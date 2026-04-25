from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, constr, Field, validator

# ----------------- ЧАТЫ -----------------


class ChatBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    is_group: bool = False

    @validator('name')
    def name_must_not_be_whitespace(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Chat name must not be only whitespace")
        return v


class ChatCreate(ChatBase):
    participants: List[UUID]


class ChatResponse(ChatBase):
    id: UUID
    name: str
    created_at: datetime
    participants: List[UUID]

    class Config:
        from_attributes = True
        orm_mode = True


# ----------------- УЧАСТНИКИ ЧАТА -----------------

class ChatParticipantBase(BaseModel):
    user_id: UUID
    chat_id: UUID
    joined_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True


# ----------------- СООБЩЕНИЯ -----------------

class MessageBase(BaseModel):
    chat_id: UUID
    content: str

    @validator('content')
    def content_length_validator(cls, v: str) -> str:
        if len(v) > 1000:
            raise ValueError("Content must be at most 1000 characters")
        return v


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: UUID
    sender_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True
