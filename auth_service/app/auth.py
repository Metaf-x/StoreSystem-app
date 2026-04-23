# auth.py
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app import logger
from app.config import SECRET_KEY
from app.models import Token

SECRET_KEY = SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_tokens(data: dict, db: Session):
    user_id = str(data.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token subject is required",
        )

    issued_at = datetime.utcnow()

    to_encode = {
        "sub": user_id,
        "token_type": "access",
    }
    access_expire = issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": access_expire})
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    refresh_token_data = {
        "sub": user_id,
        "token_type": "refresh",
    }
    refresh_expire = issued_at + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
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


def verify_token(token: str, db: Session = None):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("token_type")
        if token_type not in (None, "access"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        logger.log_message("Access token successfully decoded and verified")
        return payload

    except JWTError as e:
        logger.log_message(f"Access token decoding failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


def refresh_access_token(refresh_token: str, db: Session):
    """
    Проверяет refresh token и возвращает новый access token, если refresh token действителен.
    """
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("token_type")
        if token_type not in (None, "refresh"):
            raise HTTPException(
                status_code=403, detail="Invalid or expired refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=403, detail="Invalid or expired refresh token")

        token_record = db.query(Token).filter(
            Token.user_id == user_id,
            Token.refresh_token == refresh_token,
            Token.refresh_expires_at > datetime.utcnow()
        ).first()

        if not token_record:
            raise HTTPException(
                status_code=403, detail="Invalid or expired refresh token")

        # Генерируем новый access token без role claims.
        new_access_token = jwt.encode(
            {
                "sub": user_id,
                "token_type": "access",
                "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            },
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        # Обновляем access token в БД для совместимости с текущей схемой хранения refresh-сессий.
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
