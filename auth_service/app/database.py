# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import SQLALCHEMY_DATABASE_URI
from app import models

DATABASE_URL = SQLALCHEMY_DATABASE_URI

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    # Регистрируем таблицы из единого metadata объекта моделей.
    models.Base.metadata.create_all(bind=engine)


def get_session_local():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
