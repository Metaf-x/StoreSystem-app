# database.py
import uuid
from sqlalchemy import Column, String, Boolean, create_engine, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import SQLALCHEMY_DATABASE_URI

DATABASE_URL = SQLALCHEMY_DATABASE_URI

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():

    # Создаем таблицы поэтапно
    Base.metadata.tables['suppliers'].create(bind=engine, checkfirst=True)
    Base.metadata.tables['products'].create(bind=engine, checkfirst=True)
    Base.metadata.tables['supplier_documents'].create(
        bind=engine, checkfirst=True)
    Base.metadata.tables['warehouses'].create(bind=engine, checkfirst=True)
    Base.metadata.tables['product_warehouses'].create(
        bind=engine, checkfirst=True)


def get_session_local():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(UUID(as_uuid=True), primary_key=True,
                         # Уникальный ID поставщика (UUID)
                         default=uuid.uuid4, unique=True, index=True)
    name = Column(String, index=True)  # Название поставщика
    contact_name = Column(String)  # Имя контактного лица
    contact_email = Column(String)  # Email контактного лица
    phone_number = Column(String)  # Номер телефона поставщика
    address = Column(String)  # Адрес поставщика
    country = Column(String)  # Страна поставщика
    city = Column(String)  # Город поставщика
    website = Column(String)  # Вебсайт поставщика


class SupplierDocument(Base):
    __tablename__ = "supplier_documents"

    document_id = Column(UUID(as_uuid=True), primary_key=True,
                         default=uuid.uuid4, unique=True, index=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey(
        "suppliers.supplier_id"), nullable=False, index=True)
    document_type = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    stored_filename = Column(String, nullable=False)
    content_type = Column(String)
    file_size = Column(Integer, nullable=False)
    uploaded_by = Column(String, nullable=False)
    created_at = Column(DateTime)
    description = Column(String)


class Product(Base):
    __tablename__ = "products"

    product_id = Column(UUID(as_uuid=True), primary_key=True,
                        default=uuid.uuid4, unique=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    category = Column(String)           # Категория товара
    price = Column(Float)               # Цена товара
    stock_quantity = Column(Integer)    # Количество на складе
    supplier_id = Column(UUID(as_uuid=True), ForeignKey(
        "suppliers.supplier_id"), nullable=False)    # Поставщик товара
    is_available = Column(Boolean)      # Доступность для заказа
    created_at = Column(DateTime)       # Дата добавления товара
    updated_at = Column(DateTime)       # Дата последнего обновления информации
    weight = Column(Float)              # Вес товара
    dimensions = Column(String)         # Габариты товара (ДхШхВ)
    manufacturer = Column(String)       # Производитель товара
    image_url = Column(String)          # Ссылка на изображение товара
    # ID пользователя, добавившего товар
    user_id = Column(String, nullable=False)


class Warehouse(Base):
    __tablename__ = "warehouses"

    warehouse_id = Column(UUID(as_uuid=True), primary_key=True,
                          default=uuid.uuid4, unique=True, index=True)
    location = Column(String)           # Местоположение склада
    manager_name = Column(String)       # Имя управляющего склада
    capacity = Column(Integer)          # Вместимость склада (в ед. товаров)
    current_stock = Column(Integer)     # Текущее количество товаров на складе
    contact_number = Column(String)     # Номер телефона склада
    email = Column(String)              # Контактный email
    is_active = Column(Boolean)         # Активность склада (True/False)
    area_size = Column(Float)           # Площадь склада (в кв.м)
    created_at = Column(DateTime)       # Дата добавления склада


class ProductWarehouse(Base):
    __tablename__ = "product_warehouses"

    product_warehouse_id = Column(UUID(as_uuid=True), primary_key=True,
                                  default=uuid.uuid4, unique=True, index=True)
    product_id = Column(UUID, ForeignKey('products.product_id'), index=True)
    warehouse_id = Column(UUID, ForeignKey(
        'warehouses.warehouse_id'), index=True)
    quantity = Column(Integer)          # Количество данного товара на складе
