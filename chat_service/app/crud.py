from sqlalchemy.orm import Session
import uuid
from datetime import datetime
from typing import List
from app import models, schemas
from fastapi import HTTPException
import re
import requests
from app.config import AUTH_SERVICE_URL

# ----------------- ЧАТЫ -----------------


def is_valid_uuid(u: str) -> bool:
    try:
        val = uuid.UUID(str(u))
        return len(u) == 36  # UUID в строке должен быть длиной 36 символов
    except ValueError:
        return False


def fetch_existing_user_ids(token: str) -> list[str]:
    try:
        response = requests.get(
            f"{AUTH_SERVICE_URL}/users/",
            params={"page_size": 100},
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        data = response.json()
        users = data.get("users", data) if isinstance(data, dict) else data
        if not isinstance(users, list):
            raise HTTPException(
                status_code=500,
                detail="Unexpected auth service users response"
            )
        return [user["id"] for user in users]
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail="Auth service unavailable")


def create_chat(db: Session, chat_data: schemas.ChatCreate, token: str):
    """Создает новый чат и добавляет участников"""

    invalid_uuids = [
        uid for uid in chat_data.participants if not is_valid_uuid(str(uid))]
    if invalid_uuids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid UUIDs: {invalid_uuids}"
        )

    existing_user_ids = fetch_existing_user_ids(token)

    missing_users = [str(uid) for uid in chat_data.participants if str(
        uid) not in existing_user_ids]
    if missing_users:
        raise HTTPException(
            status_code=404,
            detail=f"Users not found in auth service: {missing_users}"
        )

    chat = models.Chat(id=uuid.uuid4(), name=chat_data.name,
                       is_group=chat_data.is_group)
    db.add(chat)
    db.commit()
    db.refresh(chat)

    # Добавляем участников

    participant_ids = []
    for user_id in chat_data.participants:
        participant = models.ChatParticipant(
            chat_id=chat.id,
            user_id=user_id,
            joined_at=datetime.utcnow()
        )
        db.add(participant)
        participant_ids.append(user_id)

    db.commit()
    return schemas.ChatResponse(
        id=chat.id,
        name=chat.name,
        is_group=chat.is_group,
        created_at=chat.created_at,
        participants=participant_ids
    )


def get_chat_by_id(db: Session, chat_id: uuid.UUID):
    """Получает чат по ID"""
    return db.query(models.Chat).filter(models.Chat.id == chat_id).first()


def get_user_chats(db: Session, user_id: uuid.UUID) -> List[schemas.ChatResponse]:
    chats = (
        db.query(models.Chat)
        .join(models.ChatParticipant)
        .filter(models.ChatParticipant.user_id == user_id)
        .all()
    )

    chat_responses = []
    for chat in chats:
        # Извлекаем только UUID участников
        participant_ids = [p.user_id for p in chat.participants]
        chat_responses.append(schemas.ChatResponse(
            id=chat.id,
            name=chat.name or "",
            is_group=chat.is_group,
            created_at=chat.created_at,
            participants=participant_ids
        ))

    return chat_responses

# ----------------- СООБЩЕНИЯ -----------------


def create_message(db: Session, chat_id: uuid.UUID, sender_id: uuid.UUID, content: str):
    """Создает новое сообщение в чате"""
    message = models.Message(
        id=uuid.uuid4(),
        chat_id=chat_id,
        sender_id=sender_id,
        content=content,
        created_at=datetime.utcnow()
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_chat_messages(db: Session, chat_id: uuid.UUID, limit: int = 50):
    """Получает последние N сообщений в чате"""
    messages = (
        db.query(models.Message)
        .filter(models.Message.chat_id == chat_id)
        .order_by(models.Message.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))


def add_user_to_chat(db: Session, chat_id: uuid.UUID, user_id: uuid.UUID, token: str):
    """Добавляет пользователя в чат с проверками"""

    # Проверка UUID
    if not is_valid_uuid(str(user_id)):
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {user_id}")

    # Проверка, существует ли пользователь
    existing_user_ids = fetch_existing_user_ids(token)
    if str(user_id) not in existing_user_ids:
        raise HTTPException(
            status_code=404, detail=f"User {user_id} not found in auth service")

    # Получение чата
    chat = get_chat_by_id(db, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Проверка количества участников
    participant_count = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id
    ).count()

    if not chat.is_group and participant_count >= 2:
        raise HTTPException(
            status_code=400,
            detail="Cannot add users to a personal chat. Convert to group chat first."
        )

    # Проверка на дубликат
    existing_participant = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == user_id
    ).first()

    if existing_participant:
        raise HTTPException(status_code=400, detail="User already in chat")

    # Добавление
    new_participant = models.ChatParticipant(chat_id=chat_id, user_id=user_id)
    db.add(new_participant)
    db.commit()
