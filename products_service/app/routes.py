# routes.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form
from fastapi.responses import FileResponse
import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID, uuid4
from app import crud, schemas, database, auth, logger, models
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_session_local, Product, ProductWarehouse
from app.config import UPLOAD_DIR, SUPPLIER_DOCUMENTS_DIR
import shutil
from typing import Optional
from datetime import datetime
from pathlib import Path


router = APIRouter()

# Создаем объект security для использования схемы авторизации Bearer
security = HTTPBearer()

# Путь для загрузки изображений
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SUPPLIER_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_SUPPLIER_DOCUMENT_TYPES = {
    "contract",
    "certificate",
    "requisites",
    "price_list",
    "other",
}
MAX_SUPPLIER_DOCUMENT_SIZE = 10 * 1024 * 1024


def _get_user_data(
    credentials: HTTPAuthorizationCredentials,
    require_admin: bool = False,
    minimum_role: str = "customer",
):
    return auth.verify_token_in_other_service(
        credentials.credentials, require_admin=require_admin, minimum_role=minimum_role)


def _get_supplier_or_404(db: Session, supplier_id: UUID):
    supplier = db.query(models.Supplier).filter(
        models.Supplier.supplier_id == supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


def _supplier_document_path(supplier_id: UUID, stored_filename: str) -> Path:
    return SUPPLIER_DOCUMENTS_DIR / str(supplier_id) / stored_filename


@router.post("/upload", summary="Upload product image")
async def upload_image(file: UploadFile = File(...), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token, minimum_role="operator")
    if not user_data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверяем формат файла
    if file.content_type not in ["image/png", "image/jpeg", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Invalid image format")

    # Сохраняем файл
    file_path = UPLOAD_DIR / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Возвращаем путь для сохранения в БД
    image_url = f"/img/{file.filename}"
    return {"imageUrl": image_url}

# ---- Маршруты для CRUD операций с продуктами ----


@router.post("/products/", response_model=schemas.Product, status_code=status.HTTP_201_CREATED, tags=["Products Service"], summary="Create a new product")
async def create_product(product: schemas.ProductCreate, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    logger.log_message(
        f"User {user_data}")
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка валидности supplier_id как UUID
    try:
        UUID(str(product.supplier_id))
    except ValueError:
        raise HTTPException(
            status_code=422, detail="Invalid format for Supplier id")

    # Проверка на существование продукта с таким же названием
    existing_product = db.query(models.Product).filter(
        func.lower(models.Product.name) == func.lower(product.name)
    ).first()
    if existing_product:
        raise HTTPException(
            status_code=422, detail="This product is already existed")

    logger.log_message(f"User {user_data} is creating a new product")
    return crud.create_product(db=db, name=product.name, description=product.description, user_id=user_data["user_id"],
                               category=product.category, price=product.price, stock_quantity=product.stock_quantity,
                               supplier_id=product.supplier_id, image_url=product.image_url, weight=product.weight,
                               dimensions=product.dimensions, manufacturer=product.manufacturer)


@router.get("/products/", response_model=list[schemas.ProductResponse], tags=["Products Service"], summary="Get all products")
def get_products(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_session_local)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token)  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    logger.log_message("Getting all products")
    return crud.get_all_products(db)


@router.get("/products/{product_id}", response_model=schemas.ProductResponse, tags=["Products Service"], summary="Get product by ID")
def get_product(product_id: str, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token)  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка, что product_id не пустой
    if not product_id.strip():
        raise HTTPException(status_code=400, detail="Product ID is required")

    # Проверка корректности UUID
    try:
        product_uuid = UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Product ID")

    logger.log_message(f"Getting product with id {product_id}")
    return crud.get_product_by_id(db, product_uuid)


@router.put("/products/{product_id}", response_model=schemas.Product, tags=["Products Service"], summary="Update product by ID")
async def update_product(product_id: str, product: schemas.ProductUpdate, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token, minimum_role="operator")
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    user_id = user_data.get("user_id") if "user_id" in user_data else None

    # Проверка, что product_id не пустой
    if not product_id.strip():
        raise HTTPException(status_code=400, detail="Product ID is required")

        # Проверка на существование продукта с таким же названием
    existing_product = db.query(models.Product).filter(
        func.lower(models.Product.name) == func.lower(product.name)
    ).first()
    if existing_product and str(existing_product.product_id) != product_id:
        raise HTTPException(
            status_code=422, detail="This product is already existed")

    # Проверка корректности UUID
    try:
        product_uuid = UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Product ID")

    logger.log_message(
        f"""User {user_id} is updating product with id {product_id}, new name: {product.name}, new description: {product.description}, new price: {product.price}""")
    return crud.update_product(db=db, product_id=product_uuid, name=product.name, description=product.description,
                               category=product.category, price=product.price, stock_quantity=product.stock_quantity,
                               supplier_id=product.supplier_id, image_url=product.image_url, weight=product.weight,
                               dimensions=product.dimensions, manufacturer=product.manufacturer)


@router.patch("/products/{product_id}", response_model=schemas.ProductPatchResponse, tags=["Products Service"], summary="Partially update availablity of product by ID")
async def partial_update_product(product_id: str, availability_data: schemas.ProductAvailabilityUpdate, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token, minimum_role="operator")
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    user_id = user_data.get("user_id") if "user_id" in user_data else None

    # Проверка, что product_id не пустой
    if not product_id.strip():
        raise HTTPException(status_code=400, detail="Product ID is required")

    # Проверка корректности UUID
    try:
        product_uuid = UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Product ID")

    logger.log_message(
        f"User {user_id} is partially updating product with id {product_id}")

    # Проверяем is_available на корректность
    if availability_data.is_available is None:
        raise HTTPException(
            status_code=400, detail="Field 'is_available' is required and cannot be null")

    # Обновите только поле is_available в crud
    updated_product = crud.update_product_availability(
        db=db, product_id=product_uuid, is_available=availability_data.is_available)

    return schemas.ProductPatchResponse(
        # Преобразуем UUID в строку
        product_id=str(updated_product.product_id),
        is_available=updated_product.is_available,
        updated_at=updated_product.updated_at,
    )


@router.delete("/products/{product_id}", tags=["Products Service"], summary="Delete product by ID")
def delete_product(product_id: str, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка, что product_id не пустой
    if not product_id.strip():
        raise HTTPException(status_code=400, detail="Product ID is required")

    # Проверка корректности UUID
    try:
        product_uuid = UUID(product_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Product ID")

    product_in_warehouse = db.query(ProductWarehouse).filter(
        ProductWarehouse.product_id == product_uuid,
    ).first()

    if product_in_warehouse:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete product {product_id}: It is available in warehouse {product_in_warehouse.warehouse_id}"
        )

    logger.log_message(f"Deleting product with id {product_id}")
    return crud.delete_product(db, product_uuid)


@router.get("/search_products/", response_model=list[schemas.Product], tags=["Products Service"], summary="Search products by name")
def search_products(name: str, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    logger.log_message(f"Searching products with name containing '{name}'")
    return crud.search_products_by_name(db, name)

# ---- CRUD операции для поставщиков (Supplier) ----


@router.post("/suppliers/", response_model=schemas.Supplier, tags=["Suppliers Service"], status_code=status.HTTP_201_CREATED, summary="Create a new supplier")
def create_supplier(supplier: schemas.SupplierCreate, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token or unauthorized access")

    # Проверка на существование поставщика с таким же названием
    existing_supplier = db.query(models.Supplier).filter(
        func.lower(models.Supplier.name) == func.lower(supplier.name)
    ).first()
    if existing_supplier:
        logger.log_message(f"""Supplier with name '{
                           supplier.name}' already exists.""")
        raise HTTPException(
            status_code=422, detail="This supplier is already existed")

    logger.log_message(f"""Creating a new supplier: {supplier.name} {
                       supplier.contact_name}, {supplier.contact_email}, {supplier.phone_number}""")
    return crud.create_supplier(db=db, name=supplier.name, contact_name=supplier.contact_name,
                                contact_email=supplier.contact_email, phone_number=supplier.phone_number,
                                address=supplier.address, country=supplier.country, city=supplier.city,
                                website=supplier.website)


@router.get("/suppliers/", response_model=list[schemas.Supplier], tags=["Suppliers Service"], summary="Get all suppliers")
def get_all_suppliers(db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token)  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    logger.log_message("Getting all suppliers")
    return crud.get_all_suppliers(db)


@router.get("/suppliers/{supplier_id}", response_model=schemas.Supplier, tags=["Suppliers Service"], summary="Get supplier by ID")
def get_supplier_by_id(supplier_id: str, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token)  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка, что supplier_id не пустой
    if not supplier_id.strip():
        raise HTTPException(status_code=400, detail="Supplier ID is required")

    # Проверка корректности UUID
    try:
        supplier_uuid = UUID(supplier_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Supplier ID")

    logger.log_message(f"Getting supplier with ID {supplier_id}")
    return crud.get_supplier_by_id(db, supplier_uuid)


@router.patch("/suppliers/{supplier_id}", response_model=schemas.Supplier, tags=["Suppliers Service"], summary="Update supplier by ID")
def patch_supplier(supplier_id: str, supplier: schemas.SupplierUpdate, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    # Передаем только те поля, которые изменены
    updates = supplier.dict(exclude_unset=True)

    # Проверка, что supplier_id не пустой
    if not supplier_id.strip():
        raise HTTPException(status_code=400, detail="Supplier ID is required")

    # Проверка корректности UUID
    try:
        supplier_uuid = UUID(supplier_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Supplier ID")

    logger.log_message(f"Updating supplier with id {supplier_id}")
    return crud.patch_supplier(db=db, supplier_id=supplier_uuid, updates=updates)


@router.delete("/suppliers/{supplier_id}", tags=["Suppliers Service"], summary="Delete supplier by ID")
def delete_supplier(supplier_id: str, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка, что supplier_id не пустой
    if not supplier_id.strip():
        raise HTTPException(status_code=400, detail="Supplier ID is required")

    # Проверка корректности UUID
    try:
        supplier_uuid = UUID(supplier_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Supplier ID")

        # Проверяем, есть ли продукты, использующие этого поставщика
    product_with_supplier = db.query(Product).filter(
        Product.supplier_id == supplier_uuid
    ).first()

    if product_with_supplier:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete supplier {supplier_id}: It is still associated with product {product_with_supplier.name} (ID: {product_with_supplier.product_id})"
        )

    supplier_document = db.query(models.SupplierDocument).filter(
        models.SupplierDocument.supplier_id == supplier_uuid
    ).first()
    if supplier_document:
        raise HTTPException(
            status_code=422,
            detail="Cannot delete supplier: there are documents linked to this supplier."
        )

    logger.log_message(f"Deleting supplier with id {supplier_id}")
    return crud.delete_supplier(db, supplier_uuid)


@router.get("/search_suppliers/", response_model=list[schemas.Supplier], tags=["Suppliers Service"], summary="Search suppliers by name")
def search_suppliers(name: str, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    logger.log_message(f"Searching suppliers with name containing '{name}'")
    return crud.search_suppliers_by_name(db, name)


@router.post("/suppliers/{supplier_id}/documents", response_model=schemas.SupplierDocument, tags=["Supplier Documents"], summary="Upload supplier document")
async def upload_supplier_document(
    supplier_id: UUID,
    document_type: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_session_local),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_data = _get_user_data(credentials, minimum_role="operator")
    _get_supplier_or_404(db, supplier_id)

    if document_type not in ALLOWED_SUPPLIER_DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="Invalid document_type")

    document_id = uuid4()
    suffix = Path(file.filename or "").suffix
    stored_filename = f"{document_id}{suffix}"
    supplier_dir = SUPPLIER_DOCUMENTS_DIR / str(supplier_id)
    supplier_dir.mkdir(parents=True, exist_ok=True)
    file_path = supplier_dir / stored_filename

    file_size = 0
    try:
        with file_path.open("wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_SUPPLIER_DOCUMENT_SIZE:
                    raise HTTPException(
                        status_code=413, detail="Document size must not exceed 10 MB")
                buffer.write(chunk)
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    document = models.SupplierDocument(
        document_id=document_id,
        supplier_id=supplier_id,
        document_type=document_type,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        content_type=file.content_type,
        file_size=file_size,
        uploaded_by=user_data["user_id"],
        created_at=datetime.utcnow(),
        description=description,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/suppliers/{supplier_id}/documents", response_model=list[schemas.SupplierDocument], tags=["Supplier Documents"], summary="List supplier documents")
def list_supplier_documents(
    supplier_id: UUID,
    db: Session = Depends(get_session_local),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    _get_user_data(credentials)
    _get_supplier_or_404(db, supplier_id)
    return db.query(models.SupplierDocument).filter(
        models.SupplierDocument.supplier_id == supplier_id
    ).order_by(models.SupplierDocument.created_at.desc()).all()


@router.get("/suppliers/{supplier_id}/documents/{document_id}/download", tags=["Supplier Documents"], summary="Download supplier document")
def download_supplier_document(
    supplier_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_session_local),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    _get_user_data(credentials)
    _get_supplier_or_404(db, supplier_id)
    document = db.query(models.SupplierDocument).filter(
        models.SupplierDocument.supplier_id == supplier_id,
        models.SupplierDocument.document_id == document_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = _supplier_document_path(supplier_id, document.stored_filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    return FileResponse(
        path=file_path,
        media_type=document.content_type or "application/octet-stream",
        filename=document.original_filename,
    )


@router.delete("/suppliers/{supplier_id}/documents/{document_id}", tags=["Supplier Documents"], summary="Delete supplier document")
def delete_supplier_document(
    supplier_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_session_local),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    _get_user_data(credentials, minimum_role="operator")
    _get_supplier_or_404(db, supplier_id)
    document = db.query(models.SupplierDocument).filter(
        models.SupplierDocument.supplier_id == supplier_id,
        models.SupplierDocument.document_id == document_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = _supplier_document_path(supplier_id, document.stored_filename)
    file_path.unlink(missing_ok=True)
    db.delete(document)
    db.commit()
    return {"message": "Document deleted"}

# ---- CRUD операции для складов (Warehouses) ----


@router.get("/warehouses/{warehouse_id}", response_model=schemas.Warehouse, tags=["Warehouses Service"], summary="Get warehouse by ID")
def get_warehouse_by_id(warehouse_id: str, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token)  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    # Проверка, что warehouse_id не пустой
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Warehouse ID is required")

    # Проверка корректности UUID
    try:
        warehouse_uuid = UUID(warehouse_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Warehouse ID")

    logger.log_message(f"Getting warehouse with id {warehouse_id}")
    return crud.get_warehouse_by_id(db, warehouse_id=str(warehouse_uuid))


@router.get("/warehouses/", response_model=list[schemas.Warehouse], tags=["Warehouses Service"], summary="Get all warehouses")
def get_all_warehouses(db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    logger.log_message("Getting all warehouses")
    return crud.get_all_warehouses(db)


@router.post("/warehouses/", response_model=schemas.Warehouse, tags=["Warehouses Service"], summary="Create a new warehouse")
def create_warehouse(warehouse: schemas.WarehouseCreate, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка на существование продукта с таким же названием
    existing_warehouse = db.query(models.Warehouse).filter(
        func.lower(models.Warehouse.location) == func.lower(warehouse.location)).first()
    if existing_warehouse:
        raise HTTPException(
            status_code=422, detail="This warehouse is already exist")

    logger.log_message(f"""Creating a new warehouse: {warehouse.location}, {warehouse.manager_name}, {warehouse.capacity}, {
                       warehouse.current_stock}, {warehouse.contact_number}, {warehouse.email}, {warehouse.is_active}, {warehouse.area_size}""")
    return crud.create_warehouse(
        db=db,
        location=warehouse.location,
        manager_name=warehouse.manager_name,
        capacity=warehouse.capacity,
        current_stock=warehouse.current_stock,
        contact_number=warehouse.contact_number,
        email=warehouse.email,
        is_active=warehouse.is_active,
        area_size=warehouse.area_size
    )


@router.patch("/warehouses/{warehouse_id}", response_model=schemas.Warehouse, tags=["Warehouses Service"], summary="Update warehouse by ID")
def patch_warehouse(warehouse_id: str, warehouse: schemas.WarehouseUpdate, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    updates = warehouse.dict(exclude_unset=True)

    # Проверка, что warehouse_id не пустой
    if not warehouse_id.strip():
        raise HTTPException(status_code=400, detail="Warehouse ID is required")

    # Проверка корректности UUID
    try:
        warehouse_uuid = UUID(warehouse_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Warehouse ID")

    logger.log_message(f"Updating warehouse with id {warehouse_id}")
    return crud.patch_warehouse(db=db, warehouse_id=warehouse_uuid, updates=updates)


@router.delete("/warehouses/{warehouse_id}", tags=["Warehouses Service"], summary="Delete warehouse by ID")
def delete_warehouse(warehouse_id: UUID, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверка, что warehouse_id не пустой
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="Warehouse ID is required")

    # Проверка корректности UUID
    try:
        warehouse_uuid = warehouse_id
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid UUID format for Warehouse ID")

    logger.log_message(f"Deleting warehouse with id {warehouse_id}")
    return crud.delete_warehouse(db, warehouse_id=str(warehouse_uuid))


# ---- CRUD операции для товаров на складах (ProductWarehouses) ----

@router.get("/productinwarehouses/{warehouse_id}", response_model=list[schemas.ProductWarehouse], tags=["Product Warehouses Service"], summary="Get products in warehouse")
def get_products_in_warehouse(warehouse_id: UUID, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token)  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    logger.log_message(f"Getting products in warehouse {warehouse_id}")
    return crud.get_products_in_warehouse(db, warehouse_id=str(warehouse_id))


@router.post("/productinwarehouses", response_model=schemas.ProductWarehouse, tags=["Product Warehouses Service"], summary="Add product to warehouse")
def add_product_to_warehouse(
        warehouse_id: UUID = Query(...),
        product_id: UUID = Query(...),
        quantity: int = Query(...),
        db: Session = Depends(get_session_local),
        credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token, minimum_role="operator")
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

    # Проверяем, что количество не отрицательное
    if quantity < 0:
        logger.log_message(f"""Attempt to add negative quantity {
                           quantity} to warehouse {warehouse_id}""")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be greater than or equal to 0"
        )

    # Проверяем, что продукт существует
    product = db.query(Product).filter(
        Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Product not found")

        # Проверяем, есть ли уже этот продукт в данном складе
    existing_entry = db.query(ProductWarehouse).filter(
        ProductWarehouse.product_id == product_id,
        ProductWarehouse.warehouse_id == warehouse_id
    ).first()

    if existing_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"""Product {product_id} is already in warehouse {
                warehouse_id}. You can only update the quantity."""
        )

    # Считаем, сколько товара уже добавлено на другие склады
    total_allocated_quantity = (
        db.query(func.sum(ProductWarehouse.quantity))
        .filter(ProductWarehouse.product_id == product_id)
        .scalar()
    ) or 0  # Если товара ещё нигде нет, считаем 0

    available_quantity = product.stock_quantity - total_allocated_quantity

    # Проверяем, что доступное количество товара позволяет добавить его на склад
    if available_quantity < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"""Not enough available stock. Total available: {
                available_quantity}, requested: {quantity}"""
        )

    logger.log_message(f"""Adding product {product_id} to warehouse {
                       warehouse_id} with quantity {quantity}""")
    return crud.add_product_to_warehouse(db=db, product_id=str(product_id), warehouse_id=str(warehouse_id), quantity=quantity)


@router.put("/productinwarehouses/{product_id}", response_model=schemas.ProductWarehouse, tags=["Product Warehouses Service"], summary="Update product in warehouse")
def update_product_in_warehouse(
        product_id: UUID,
        product_warehouse_id: UUID,
        quantity: int,
        db: Session = Depends(get_session_local),
        credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")

        # Проверяем, что количество не отрицательное
    if quantity < 0:
        logger.log_message(f"""Attempt to update product {product_id} in warehouse {
                           product_warehouse_id} with negative quantity {quantity}""")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be greater than or equal to 0"
        )

        # Проверяем, что продукт существует
    product = db.query(Product).filter(
        Product.product_id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Проверяем, что запись в ProductWarehouse существует
    product_warehouse = db.query(ProductWarehouse).filter(
        ProductWarehouse.product_warehouse_id == product_warehouse_id,
        ProductWarehouse.product_id == product_id
    ).first()

    if not product_warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Product in warehouse not found")

        # Считаем, сколько этого продукта уже распределено по складам (кроме текущего обновляемого склада)
    total_allocated_quantity = (
        db.query(func.sum(ProductWarehouse.quantity))
        .filter(ProductWarehouse.product_id == product_id)
        # Исключаем текущий склад
        .filter(ProductWarehouse.product_warehouse_id != product_warehouse_id)
        .scalar()
    ) or 0  # Если товара ещё нигде нет, считаем 0

    available_quantity = product.stock_quantity - total_allocated_quantity

    # Проверяем, что доступное количество товара позволяет обновить его в этом складе
    if available_quantity < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"""Not enough available stock. Total available: {
                available_quantity}, requested update: {quantity}"""
        )

    logger.log_message(f"Updating product in warehouse {product_warehouse_id}")
    return crud.update_product_in_warehouse(
        db=db,
        product_id=str(product_id),
        product_warehouse_id=str(product_warehouse_id),
        quantity=quantity
    )


@router.delete("/productinwarehouses/{product_id}", tags=["Product Warehouses Service"], summary="Delete product from warehouse")
def delete_product_from_warehouse(product_warehouse_id: UUID, product_id: UUID, db: Session = Depends(get_session_local), credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(
        token, minimum_role="operator")  # Проверяем токен через auth.py
    if not user_data:
        logger.log_message("Invalid token or unauthorized access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Invalid token or unauthorized access")
    logger.log_message(f"""Deleting product from warehouse {
                       product_warehouse_id}""")
    return crud.delete_product_from_warehouse(db, product_id=str(product_id), product_warehouse_id=str(product_warehouse_id))


@router.get("/productinwarehouses/{warehouse_id}/products", response_model=list[schemas.ProductFilter])
def get_products_in_warehouse_with_filters(
    warehouse_id: UUID,
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    in_stock: Optional[bool] = Query(None),
    name: Optional[str] = Query(None),
    db: Session = Depends(get_session_local),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials
    user_data = auth.verify_token_in_other_service(token)
    if not user_data:
        raise HTTPException(status_code=403, detail="Unauthorized")

    query = (
        db.query(Product, ProductWarehouse.quantity)
        .join(ProductWarehouse, Product.product_id == ProductWarehouse.product_id)
        .filter(ProductWarehouse.warehouse_id == warehouse_id)
    )

    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if in_stock:
        query = query.filter(ProductWarehouse.quantity > 0)
    if name:
        query = query.filter(Product.name.ilike(f"%{name}%"))

    products = query.all()

    return [schemas.ProductFilter.from_orm(product, quantity) for product, quantity in products]
