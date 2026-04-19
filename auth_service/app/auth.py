# auth.py
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from passlib.context import CryptContext
from app.config import SECRET_KEY
from app import logger
from app.models import Token

SECRET_KEY = SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_tokens(data: dict, db: Session):
    user_id = data.get("sub")
    issued_at = datetime.utcnow()

    to_encode = data.copy()
    access_expire = issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": access_expire})
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    refresh_expire = issued_at + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_data = data.copy()
    refresh_token_data.update({"exp": refresh_expire})
    refresh_token = jwt.encode(
        refresh_token_data, SECRET_KEY, algorithm=ALGORITHM)

    token_values = {
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "created_at": issued_at,
        "expires_at": access_expire,
        "refresh_expires_at": refresh_expire,
    }

    # Upsert the token row atomically so concurrent logins cannot race between delete and insert.
    insert_stmt = pg_insert(Token.__table__).values(token_values)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[Token.__table__.c.user_id],
        set_={
            "access_token": insert_stmt.excluded.access_token,
            "refresh_token": insert_stmt.excluded.refresh_token,
            "created_at": insert_stmt.excluded.created_at,
            "expires_at": insert_stmt.excluded.expires_at,
            "refresh_expires_at": insert_stmt.excluded.refresh_expires_at,
        },
    )
    db.execute(upsert_stmt)
    db.commit()

    logger.log_message(f"Created new access and refresh tokens for: {user_id}")
    return {"access_token": access_token, "refresh_token": refresh_token}


def verify_token(token: str, db: Session):
    logger.log_message(f"verify_token called with token: {token} and db: {db}")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        # Проверяем, что токен активен, существует и не истек
        token_record = db.query(Token).filter(
            Token.user_id == user_id, Token.access_token == token).first()
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Inactive, expired, or invalid token"
            )

        logger.log_message(
            f"Token successfully decoded and verified: {payload}")
        return payload

    except JWTError as e:
        logger.log_message(f"Token decoding failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def refresh_access_token(refresh_token: str, db: Session):
    """
    Проверяет refresh token и возвращает новый access token, если refresh token действителен.
    """
    try:
        # Декодируем refresh token и извлекаем user_id
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        # Проверка наличия токена в БД и его срока действия
        token_record = db.query(Token).filter(
            Token.user_id == user_id,
            Token.refresh_token == refresh_token,
            Token.refresh_expires_at > datetime.utcnow()
        ).first()

        if not token_record:
            raise HTTPException(
                status_code=403, detail="Invalid or expired refresh token")

        # Генерируем новый access token
        new_access_token = jwt.encode(
            {"sub": user_id, "exp": datetime.utcnow(
            ) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        # Обновляем access token в БД
        token_record.access_token = new_access_token
        token_record.expires_at = datetime.utcnow(
        ) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        db.commit()

        return {"user_id": user_id, "access_token": new_access_token}
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid refresh token")


def revoke_refresh_token(refresh_token: str, db: Session):
    db.query(Token).filter(Token.refresh_token == refresh_token).delete()
    db.commit()


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)
