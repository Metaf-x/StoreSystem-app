# crud.py
from sqlalchemy.orm import Session
from app.models import User, Token
from app.schemas import UserCreate, UserUpdate
from app.auth import get_password_hash
import uuid
from app import logger, schemas
from psycopg2 import sql
from sqlalchemy import case, or_
from typing import Optional


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email.lower()).first()


def create_user(db: Session, user: UserCreate, is_superadmin: bool = False):
    hashed_password = get_password_hash(user.password)
    db_user = User(id=uuid.uuid4(), email=user.email,
                   name=user.name, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.log_message(
        f"""A user has been created in the database: {user.email}""")

    # Создаем пользователя в PostgreSQL с ролью limited_user
    assign_role_to_user(db, user.email, user.password)

    return db_user


def assign_role_to_user(db: Session, email: str, password: str):
    role_name = email.strip().lower()

    # Открываем сырое SQL-соединение, чтобы выполнить SQL-запросы напрямую
    with db.connection().connection.cursor() as cursor:
        # SQL-запрос для создания нового пользователя в PostgreSQL и присвоения ему роли
        cursor.execute(
            sql.SQL("CREATE USER {} WITH PASSWORD %s").format(
                sql.Identifier(role_name)
            ),
            (password,),
        )
        cursor.execute(
            sql.SQL("GRANT limited_user TO {}").format(
                sql.Identifier(role_name)
            )
        )
        db.commit()
        logger.log_message(
            f"A user {role_name} has been created in PostgreSQL with role limited_user")


def drop_role_for_user(db: Session, email: str):
    role_name = email.strip().lower()

    with db.connection().connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("DROP USER IF EXISTS {}").format(
                sql.Identifier(role_name)
            )
        )


def promote_to_superadmin(db: Session, user_id: uuid.UUID):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    user.is_superadmin = True
    db.commit()
    db.refresh(user)
    logger.log_message(
        f"A user {user.email} promoted to super admin in the database")
    return user


def get_users_for_superadmin(
    db: Session,
    search: Optional[str] = None,
    role: Optional[str] = None,
    sort_by: str = "name",
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 10,
):
    query = db.query(User)

    if role == "superadmin":
        query = query.filter(User.is_superadmin.is_(True))
    elif role == "user":
        query = query.filter(User.is_superadmin.is_(False))

    if search:
        search_value = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.name.ilike(search_value),
                User.email.ilike(search_value),
            )
        )

    total = query.count()

    sort_map = {
        "id": User.id,
        "name": User.name,
        "email": User.email,
        "role": case((User.is_superadmin.is_(True), 1), else_=0),
    }

    sort_column = sort_map.get(sort_by, User.name)
    if sort_order == "desc":
        sort_expression = sort_column.desc()
    else:
        sort_expression = sort_column.asc()

    users = (
        query.order_by(sort_expression, User.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return users, total


def get_user_by_id(db: Session, user_id: uuid.UUID):
    return db.query(User).filter(User.id == user_id).first()


def edit_user(db: Session, user_id: str, user_data: UserUpdate):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # Обновляем только те поля, которые переданы в запросе
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.name is not None:
        user.name = user_data.name

    db.commit()
    db.refresh(user)
    logger.log_message(f"User {user.email} has been updated in the database")
    return user


def delete_user(db: Session, user_id: str):  # Удаление пользователя
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Возвращаем None, если пользователь не найден
        return None

    user_email = user.email

    # Удаляем связанные токены пользователя
    token = db.query(Token).filter(Token.user_id == str(user_id)).first()
    if token:
        db.delete(token)

    drop_role_for_user(db, user_email)
    db.delete(user)
    db.commit()
    logger.log_message(
        f"User {user_email} has been deleted from the database")
    return user
