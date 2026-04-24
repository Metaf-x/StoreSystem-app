# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import (
    SEED_SUPERADMIN_EMAIL,
    SEED_SUPERADMIN_ENABLED,
    SEED_SUPERADMIN_NAME,
    SEED_SUPERADMIN_PASSWORD,
    SQLALCHEMY_DATABASE_URI,
)
from app import crud, logger, models, schemas

DATABASE_URL = SQLALCHEMY_DATABASE_URI

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    # Регистрируем таблицы из единого metadata объекта моделей.
    models.Base.metadata.create_all(bind=engine)
    seed_superadmin()


def seed_superadmin():
    if not SEED_SUPERADMIN_ENABLED:
        logger.log_message("Seed superadmin is disabled.")
        return None

    db = SessionLocal()
    try:
        email = SEED_SUPERADMIN_EMAIL.strip().lower()
        existing_user = crud.get_user_by_email(db, email)
        if existing_user:
            if not existing_user.is_superadmin:
                existing_user.is_superadmin = True
                db.commit()
                db.refresh(existing_user)
                logger.log_message(
                    f"Existing seed user {email} promoted to super admin."
                )
            return existing_user

        seed_user = schemas.UserCreate(
            name=SEED_SUPERADMIN_NAME,
            email=email,
            password=SEED_SUPERADMIN_PASSWORD,
        )
        created_user = crud.create_user(
            db=db,
            user=seed_user,
            is_superadmin=True,
        )
        logger.log_message(f"Seed superadmin {email} has been created.")
        return created_user
    except Exception as exc:
        logger.log_message(f"Seed superadmin failed: {exc}")
        raise
    finally:
        db.close()


def get_session_local():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
