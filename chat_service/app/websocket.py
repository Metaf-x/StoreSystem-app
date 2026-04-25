# websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Dict
from uuid import UUID
from sqlalchemy.orm import Session
import json

from app import crud, schemas, auth
from app.database import get_db, redis_client
from app import logger
from app.kafka import send_chat_notification
from app import models

router = APIRouter()

# Хранилище активных WebSocket-соединений
active_connections: Dict[UUID, WebSocket] = {}


# Подключение к Redis
CHAT_HISTORY_KEY = "chat_history"


def prefill_redis_with_history(db: Session):
    """
    Заполняет Redis последними 50 сообщениями для каждого чата из БД
    """
    chats = db.query(models.Chat).all()
    for chat in chats:
        # Берём последние 50 сообщений по убыванию даты
        messages = (
            db.query(models.Message)
            .filter(models.Message.chat_id == chat.id)
            .order_by(models.Message.created_at.desc())
            .limit(50)
            .all()
        )

        # Redis хранит сообщения в виде LIFO, а мы хотим,
        # чтобы "новейшее" было в начале списка, значит lpush(...).
        # Но messages сейчас идут от "новых" к "старым".
        # Т. е. мы хотим lpush от самого старого к самому новому,
        # чтобы в списке первым шёл самый свежий.
        # Поэтому реверсим и пушим в порядке (от самого старого к новому).
        for msg in reversed(messages):
            redis_client.lpush(
                f"{CHAT_HISTORY_KEY}:{str(chat.id)}",
                json.dumps({
                    "id": str(msg.id),
                    "chat_id": str(msg.chat_id),
                    "sender_id": str(msg.sender_id),
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }, ensure_ascii=False))


async def send_message_to_chat(chat_id: UUID, message: dict):
    """Отправка сообщения всем участникам чата"""
    for user_id, websocket in active_connections.items():
        if str(user_id) in message["participants"]:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))


@router.websocket("/ws/{chat_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str, user_id: str, db: Session = Depends(get_db)):
    """WebSocket-соединение для общения в чате"""
    try:
        chat_uuid = UUID(chat_id)
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        token_data = auth.verify_token_in_other_service(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    if token_data.get("user_id") != str(user_uuid):
        await websocket.close(code=1008)
        return

    # Проверяем, есть ли пользователь в чате
    chat = crud.get_chat_by_id(db, chat_uuid)
    if not chat:
        await websocket.close(code=1008)
        return

    if user_uuid not in [p.user_id for p in chat.participants]:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    active_connections[user_uuid] = websocket

    logger.log_message(f"User {user_uuid} connected to chat {chat_id}")

    # =======================================
    # 1. Отправляем последние 50 сообщений из Redis
    # =======================================

    # LREDIS: lpush() добавляет новые сообщения «в начало» списка,
    # значит индексы 0..49 - это 50 самых последних сообщений.
    stored_messages = redis_client.lrange(
        f"{CHAT_HISTORY_KEY}:{chat_id}", 0, 49)

    # lrange вернёт список байтов, нужно декодировать и распарсить JSON:
    stored_messages_parsed = [json.loads(msg) for msg in stored_messages]
    stored_messages_parsed.reverse()

    # Отправляем каждое сообщение по очереди текущему пользователю:
    for msg in stored_messages_parsed:
        await websocket.send_text(json.dumps(msg, ensure_ascii=False))

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            content = message_data["content"]
            if not content:
                await websocket.send_text(json.dumps({
                    "error": "Missing required field: content"
                }, ensure_ascii=False))
                continue

            if len(content) > 1000:
                await websocket.send_text(json.dumps({"error": "Content must be at most 1000 characters"}, ensure_ascii=False))
                continue

            # Создаем сообщение в БД
            message = crud.create_message(
                db=db,
                chat_id=chat_uuid,
                sender_id=user_uuid,
                content=content
            )

            # Отправляем уведомление в Kafka
            send_chat_notification(chat_uuid, user_uuid, message.content)

            # Сохраняем сообщение в Redis
            redis_client.lpush(f"{CHAT_HISTORY_KEY}:{chat_id}", json.dumps({
                "id": str(message.id),
                "chat_id": str(chat_uuid),
                "sender_id": str(user_uuid),
                "content": message.content,
                "created_at": message.created_at.isoformat()
            }, ensure_ascii=False))

            # Отправляем сообщение всем участникам
            message_response = {
                "id": str(message.id),
                "chat_id": str(chat_uuid),
                "sender_id": str(user_uuid),
                "content": message.content,
                "created_at": message.created_at.isoformat(),
                "participants": [str(p.user_id) for p in chat.participants]
            }
            await send_message_to_chat(chat_uuid, message_response)

    except WebSocketDisconnect:
        logger.log_message(
            f"User {user_uuid} disconnected from chat {chat_id}")
        active_connections.pop(user_uuid, None)
