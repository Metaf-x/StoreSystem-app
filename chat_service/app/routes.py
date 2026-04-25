from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app import schemas, crud, models, auth
from app.database import get_db
from app import logger

router = APIRouter()
security = HTTPBearer()


# ---- Маршрут для создания чата ----
@router.post("/chats/", response_model=schemas.ChatResponse, status_code=status.HTTP_201_CREATED, tags=["Chat Service"], summary="Create a new chat")
async def create_chat(chat_data: schemas.ChatCreate, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")
    user_id = user_data["user_id"]

    if not user_data:
        logger.log_message("Unauthorized access attempt")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверяем, что в чате есть хотя бы два участника
    if len(chat_data.participants) < 2:
        raise HTTPException(
            status_code=400, detail="A chat must have at least two participants")

        # Проверяем, что нет повторяющихся user_id
    if len(set(chat_data.participants)) != len(chat_data.participants):
        raise HTTPException(
            status_code=400,
            detail="Participants must not contain duplicate user IDs."
        )

    if len(chat_data.participants) > 2 and not chat_data.is_group:
        raise HTTPException(
            status_code=400,
            detail="Chat with more than two participants must be marked as a group chat (is_group=True)"
        )

    # Создание чата
    logger.log_message(f"Admin {user_id} is creating a chat")
    return crud.create_chat(db=db, chat_data=chat_data, token=token)


# ---- Маршрут для получения всех чатов пользователя ----
@router.get("/chats/", response_model=List[schemas.ChatResponse], tags=["Chat Service"], summary="Get all user chats")
async def get_user_chats(db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        logger.log_message("Unauthorized access attempt")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    user_id = user_data["user_id"]

    logger.log_message(f"User {user_id} is fetching their chats")
    return crud.get_user_chats(db, user_id=user_id)


# ---- Маршрут для получения информации о чате ----
@router.get("/chats/{chat_id}", tags=["Chat Service"], summary="Get chat")
def get_chat_by_id_route(chat_id: UUID, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(security)):

    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        logger.log_message("Unauthorized access attempt")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    # Проверка валидности UUID
    # try:
    #     valid_chat_id = UUID(chat_id)
    # except ValueError:
    #     raise HTTPException(status_code=422, detail="Invalid UUID format")

    chat = crud.get_chat_by_id(db, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    current_user_uuid = UUID(user_data["user_id"])
    if user_data.get("role") not in {"operator", "admin"} and not any(
        participant.user_id == current_user_uuid for participant in chat.participants
    ):
        raise HTTPException(
            status_code=403,
            detail="User is not a participant of this chat"
        )
    return {
        "id": str(chat.id),
        "name": chat.name,
        "is_group": chat.is_group,
        "participants": [str(p.user_id) for p in chat.participants],
        # если нужно, можно вернуть messages и т.п.
    }


# ---- Маршрут для получения сообщений в чате ----
@router.get("/chats/{chat_id}/messages", response_model=List[schemas.MessageResponse], tags=["Chat Service"], summary="Get chat messages")
async def get_chat_messages(chat_id: str, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        logger.log_message("Unauthorized access attempt")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка корректности UUID
    try:
        chat_uuid = UUID(chat_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Chat ID")

    # Получаем чат, чтобы проверить участников
    chat = crud.get_chat_by_id(db, chat_uuid)
    if not chat:
        raise HTTPException(
            status_code=404,
            detail="Chat not found"
        )

    # Превращаем user_data["user_id"] в UUID
    try:
        current_user_uuid = UUID(user_data["user_id"])
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for user_id")

    # Проверяем, что пользователь состоит в чате
    if user_data.get("role") not in {"operator", "admin"} and not any(participant.user_id == current_user_uuid for participant in chat.participants):
        raise HTTPException(
            status_code=403,
            detail="User is not a participant of this chat"
        )

    logger.log_message(
        f"User {user_data} is fetching messages for chat {chat_id}")
    return crud.get_chat_messages(db, chat_uuid)


# ---- Маршрут для отправки сообщения ----
@router.post("/chats/{chat_id}/messages", response_model=schemas.MessageResponse, status_code=status.HTTP_201_CREATED, tags=["Chat Service"], summary="Send a message in a chat")
async def send_message(chat_id: str, message_data: schemas.MessageCreate, db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        logger.log_message("Unauthorized access attempt")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка корректности UUID
    try:
        chat_uuid = UUID(chat_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Chat ID")

    # Проверка, состоит ли пользователь в чате
    chat = crud.get_chat_by_id(db, chat_uuid)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Преобразуем user_data["user_id"] в UUID
    try:
        current_user_uuid = UUID((user_data["user_id"]))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid UUID format for user_id"
        )

    # Проверка, состоит ли пользователь в чате
    if not any(participant.user_id == current_user_uuid for participant in chat.participants):
        raise HTTPException(
            status_code=403,
            detail="User is not a participant of this chat"
        )

    # Создание сообщения
    logger.log_message(
        f"User {user_data} is sending a message in chat {chat_id}")
    new_message = crud.create_message(
        db=db,
        chat_id=chat_uuid,
        sender_id=current_user_uuid,   # Берём только из токена
        content=message_data.content   # Это поле из схемы
    )

    # Возвращаем то, что подходит под schemas.MessageResponse
    return schemas.MessageResponse(
        id=new_message.id,
        chat_id=new_message.chat_id,
        content=new_message.content,
        created_at=new_message.created_at
    )

# ---- Маршрут для добавления пользователя в чат ----


@router.patch("/chats/add_user", status_code=status.HTTP_200_OK, tags=["Chat Service"], summary="Add a user to a chat")
def add_user_to_chat(
    chat_id: UUID = Query(...,
                          description="ID чата, в который добавляется пользователь"),
    user_id: UUID = Query(...,
                          description="ID пользователя, которого нужно добавить"),
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")

    if not user_data:
        logger.log_message("Unauthorized access attempt")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    """Добавляет пользователя в чат"""

    # Добавляем пользователя в чат
    crud.add_user_to_chat(db=db, chat_id=chat_id, user_id=user_id, token=token)

    logger.log_message(f"""Admin {user_data['user_id']} added user {
                       user_id} to chat {chat_id}""")

    return {"message": "User added to chat successfully"}
