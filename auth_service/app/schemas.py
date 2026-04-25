# schemas.py
from pydantic import BaseModel
from pydantic import BaseModel, EmailStr, constr, validator, Field
import re
from typing import Literal, Optional
from uuid import UUID


UserRole = Literal["customer", "operator", "admin"]


class UserCreate(BaseModel):
    # Минимум 3, максимум 50 символов для имени
    name: constr(min_length=3, max_length=50)
    email: EmailStr  # Email должен быть валидным
    # Ограничение на длину пароля (например, минимум 8 символов)
    password: constr(min_length=8)

    @validator("name")
    def validate_name(cls, value):
        # Регулярное выражение для проверки: минимум 3 символа, без строк из пробелов или начальных пробелов
        pattern = r'^(?!\s*$)(?!\s).{3,50}$'
        if not re.match(pattern, value):
            raise ValueError("Name contains invalid characters.")
        return value

    @validator("password")
    def validate_password(cls, value):
        # Регулярное выражение для проверки: минимум 3 символа, без строк из пробелов или начальных пробелов
        pattern = r'^(?!\s*$)(?!\s).{3,50}$'
        if not re.match(pattern, value):
            raise ValueError("Password contains invalid characters.")
        return value

    @validator("email")
    def validate_email(cls, value):
        email = value.strip().lower()

        # Разделим email на локальную и доменную части
        if '@' not in email:
            raise ValueError("Invalid email format.")

        local, domain = email.split('@', 1)

        # Проверка локальной части
        if not re.match(r"^[a-zA-Z0-9](?!.*\.\.)[a-zA-Z0-9!#$%&'*+/=?^_`{|}~.-]{0,62}[a-zA-Z0-9]$", local):
            raise ValueError("Invalid local part in email.")

        # Проверка доменной части
        if not re.match(r"^(?!-)([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", domain):
            raise ValueError("Invalid domain in email.")

        return email

    class Config:
        orm_mode = True  # Для работы с ORM (если используется SQLAlchemy)


class User(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: UserRole = "customer"


class RegistrationResponse(BaseModel):
    message: str
    user: User


class Login(BaseModel):  # Модель для аутентификации пользователя (логин)
    email: EmailStr
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    user_id: str
    message: str
    access_token: str
    token_type: str = "bearer"

    class Config:
        schema_extra = {
            "example": {
                "user_id": "8d14a7ed-353c-4d58-9990-301d4c79665e",
                "message": "User successfully logged in",
                "access_token": "your_access_token",
                "token_type": "bearer"
            }
        }


# Модель для ответа с токеном
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenResponseSchema(BaseModel):
    user_id: Optional[str] = None
    access_token: Optional[str] = None


class TokenRequestSchema(BaseModel):
    token: str = Field(..., example="your_access_token")


class TokenValidationResponseSchema(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    role: Optional[UserRole] = None
    error: Optional[str] = None


class LogoutResponseSchema(BaseModel):
    detail: str


class MeResponseSchema(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole


class UserUpdate(BaseModel):
    email: Optional[EmailStr]  # Email является необязательным
    # Имя также является необязательным
    name: Optional[constr(min_length=3, max_length=50)]

    @validator("name")
    def validate_name(cls, value):
        # Регулярное выражение для проверки: минимум 3 символа, без строк из пробелов или начальных пробелов
        pattern = r'^(?!\s*$)(?!\s).{3,50}$'
        if not re.match(pattern, value):
            raise ValueError("Name contains invalid characters.")
        return value

    @validator("email")
    def validate_email(cls, value):
        # Проверка первой части email до знака @
        local_part_pattern = (
            r"^(?!\.)(?!.*\.\.)([a-zA-Z0-9!#$%&'*+/=?^_`{|}~.-]+)(?<!\.)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})$"
        )
        if not re.match(local_part_pattern, value):
            raise ValueError("Invalid email format.")
        return value.lower()  # Приводим к нижнему регистру для единого хранения

    class Config:
        orm_mode = True


class UserUpdateResponse(BaseModel):
    detail: str
    user: User


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole

    class Config:
        orm_mode = True


class PaginatedUserResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProductIdSchema(BaseModel):
    product_id: str


class UserRoleUpdate(BaseModel):
    role: UserRole
