# routes.py
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Path, Query
import uuid
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app import crud, schemas, database, auth, logger, kafka
from app.models import User
from fastapi.responses import JSONResponse
from app.database import get_session_local
import requests
import redis
from typing import Optional
from app.approval_queue import remove_product_from_pending


router = APIRouter()
templates = Jinja2Templates(directory="templates")
redis_client = redis.Redis(host='redis', port=6379, db=0)
ROLE_ORDER = {"customer": 0, "operator": 1, "admin": 2}

# Создаем объект security для использования схемы авторизации Bearer
security = HTTPBearer()


def _require_role(user: User, minimum_role: str):
    role = getattr(user, "role", "customer")
    if ROLE_ORDER.get(role, -1) < ROLE_ORDER[minimum_role]:
        raise HTTPException(status_code=403, detail="Insufficient rights")
    return user


def get_current_user(
    db: Session = Depends(get_session_local),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token_data = auth.verify_token(credentials.credentials, db=db)
    user = crud.get_user_by_id(db, uuid.UUID(token_data["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)):
    return _require_role(current_user, "admin")


def require_operator(current_user: User = Depends(get_current_user)):
    return _require_role(current_user, "operator")


@router.post("/remove-from-pending/", tags=["Approval"], summary="Remove product from approval queue")
def remove_from_pending(product: schemas.ProductIdSchema, current_user: User = Depends(require_operator)):
    """
    Удаляет product_id из очереди на одобрение в Redis.
    """
    product_id = product.product_id
    if not product_id:
        raise HTTPException(status_code=400, detail="Product ID is required")

    try:
        remove_product_from_pending(product_id)
        return {"message": f"Product ID {product_id} removed from Redis pending queue."}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error removing product from Redis: {str(e)}")


@router.post("/refresh-token", response_model=schemas.TokenResponseSchema, tags=["Auth"], summary="Refresh access token")
async def refresh_token_endpoint(request: Request, db: Session = Depends(get_session_local)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return {"user_id": None, "access_token": None}

    try:
        # Получаем новый access token
        return auth.refresh_access_token(refresh_token, db)
    except HTTPException:
        return {"user_id": None, "access_token": None}


@router.post("/logout", response_model=schemas.LogoutResponseSchema, tags=["Auth"], summary="Logout current user")
async def logout(request: Request, response: Response, db: Session = Depends(get_session_local)):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        auth.revoke_refresh_token(refresh_token, db)

    response.delete_cookie(key="refresh_token", path="/")
    return {"detail": "Logged out"}


# Рендеринг страницы регистрации
@router.get("/register", include_in_schema=False)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_model=schemas.RegistrationResponse, status_code=status.HTTP_201_CREATED, responses={
    201: {"description": "User successfully created", "model": schemas.RegistrationResponse},
    422: {"description": "Email already registered or invalid data"},
}, tags=["Profile"], summary="Register new user")
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_session_local)):
    try:
        user_email = user.email.lower()
        db_user = crud.get_user_by_email(db, email=user_email)
        if db_user:
            logger.log_message(f"""Registration failed: email {
                user.email} is already existed.""")
            raise HTTPException(
                status_code=422, detail="Email already registered")

        # Проверка имени пользователя
        if not user.name.strip():
            raise HTTPException(
                status_code=422, detail="Name contains invalid characters."
            )
        # Проверка пароля
        if not user.password.strip():
            raise HTTPException(
                status_code=422, detail="Password contains invalid characters."
            )
        # Проверка email
        if not user.email.strip():
            raise HTTPException(
                status_code=422, detail="Invalid email format."
            )

        # Суперадмин не может быть установлен через регистрацию
        created_user = crud.create_user(db=db, user=user.copy(
            update={"email": user_email}), role="customer")
        logger.log_message(f"User is registered: {user.email}")

        # Перенаправляем на страницу авторизации
        return {
            "message": "User successfully created",
            "user": {
                "id": created_user.id,
                "name": created_user.name,
                "email": created_user.email,
                "role": created_user.role,
            }
        }
    except HTTPException as http_exc:
        # Логируем исключение с конкретным кодом ошибки
        raise http_exc
    except Exception as e:
        logger.log_message(f"An error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Рендеринг страницы авторизации
@router.get("/login", include_in_schema=False)
def register_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# Авторизация пользователя и перенаправление на страницу store
@router.post("/login", response_model=schemas.LoginResponse, tags=["Auth"], summary="Login in system", responses={
    200: {"description": "User successfully logged in", "model": schemas.LoginResponse},
    400: {"description": "Invalid email or password"}
})
def login_for_access_token(
    form_data: schemas.Login,
    response: Response,
    db: Session = Depends(database.get_session_local)
):
    user = crud.get_user_by_email(db, email=form_data.email)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        logger.log_message(f"""Failed login attempt for email: {
                           form_data.email}""")
        raise HTTPException(
            status_code=400, detail="Invalid email or password")

    user_id_str = str(user.id)
    tokens = auth.create_tokens(
        data={"sub": user_id_str}, db=db)

    cookie_kwargs = {
        "key": "refresh_token",
        "value": tokens["refresh_token"],
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "secure": False,
    }
    if form_data.remember_me:
        cookie_kwargs["max_age"] = auth.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    response.set_cookie(**cookie_kwargs)

    logger.log_message(f"User is logged in: {form_data.email}")

    return {
        "user_id": user_id_str,
        "message": "User successfully logged in",
        "access_token": tokens["access_token"],
        "token_type": "bearer"
    }


@router.put("/users/{user_id}/role", status_code=200, tags=["Admin"], summary="Update user role", responses={
    200: {"description": "User role successfully updated", "content": {"application/json": {"example": {"detail": "User role successfully updated"}}}},
    400: {"description": "Bad Request - User ID is required", "content": {"application/json": {"example": {"detail": "User ID is required"}}}},
    403: {"description": "Insufficient rights", "content": {"application/json": {"example": {"detail": "Insufficient rights"}}}},
    404: {"description": "User not found", "content": {"application/json": {"example": {"detail": "User not found"}}}},
    422: {"description": "Invalid UUID format", "content": {"application/json": {"example": {"detail": "Invalid UUID format"}}}},
})
def update_user_role(
    user_id: str,
    form_data: schemas.UserRoleUpdate,
    db: Session = Depends(get_session_local),
    requesting_user: User = Depends(require_admin),
):
    # Проверка, что user_id не пустой
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="User ID is required")

    # Проверка, что user_id имеет корректный формат UUID
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID format")

    user = crud.get_user_by_id(db, user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == form_data.role:
        return {"detail": "User already has this role", "role": user.role}

    if user.role == "admin" and form_data.role != "admin" and crud.count_users_by_role(db, "admin") <= 1:
        raise HTTPException(
            status_code=403, detail="Cannot remove the last admin role")

    updated_user = crud.update_user_role(db, user_uuid, form_data.role)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")

    logger.log_message(
        f"Admin {requesting_user.email} changed user {updated_user.email} role to {updated_user.role}.")
    return {"detail": "User role successfully updated", "role": updated_user.role}


# Получение списка пользователей (только для супер-админа)
@router.get("/users", response_model=schemas.PaginatedUserResponse, tags=["Admin"], summary="Get users")
def get_users(
    db: Session = Depends(get_session_local),
    requesting_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("name"),
    order: str = Query("asc"),
    search: Optional[str] = Query(default=None, max_length=200),
    role: Optional[str] = Query(default=None),
):
    if requesting_user.role == "admin":
        allowed_sort_fields = {"id", "name", "email", "role"}
        if sort_by not in allowed_sort_fields:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort field: {sort_by}"
            )

        order_value = order.lower()
        if order_value not in {"asc", "desc"}:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported sort order: {order}"
            )

        allowed_role_filters = {None, "", "all", "customer", "operator", "admin"}
        if role not in allowed_role_filters:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported role filter: {role}"
            )

        users, total = crud.get_users_for_superadmin(
            db=db,
            search=search,
            role=None if role in {None, "", "all"} else role,
            sort_by=sort_by,
            sort_order=order_value,
            page=page,
            page_size=page_size,
        )
    else:
        # Non-superadmins only see their own record.
        users = [requesting_user]
        total = 1
        page = 1
        page_size = 1
        role = "customer"

    result = []
    for user in users:
        result.append({
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
        })

    total_pages = (total + page_size - 1) // page_size if total else 0

    return {
        "users": result,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# Пример маршрута для редактирования пользователя с проверкой токена через HTTPBearer
@router.put("/users/edit/{user_id}", response_model=schemas.UserUpdateResponse, responses={
    200: {"description": "User successfully updated", "model": schemas.UserUpdateResponse},
    400: {"description": "Bad Request - User ID is required", "content": {"application/json": {"example": {"detail": "User ID is required"}}}},
    403: {"description": "Insufficient rights", "content": {"application/json": {"example": {"detail": "Insufficient rights"}}}},
    404: {"description": "User not found", "content": {"application/json": {"example": {"detail": "User not found"}}}},
    422: {"description": "Invalid UUID format", "content": {"application/json": {"example": {"detail": "Invalid UUID format"}}}},
    422: {"description": "Email already registered", "content": {"application/json": {"example": {"detail": "Email already registered"}}}},
}, tags=["Admin"], summary="Edit user")
def edit_user(user_id: str, form_data: schemas.UserUpdate, db: Session = Depends(get_session_local), requesting_user: User = Depends(require_admin)):

    # Проверка, что user_id не пустой
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="User ID is required")

    # Проверка корректности UUID
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    # Проверяем, существует ли пользователь с таким user_id
    user = crud.get_user_by_id(db, user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверка на уникальность email
    if form_data.email:
        existing_user = crud.get_user_by_email(db, form_data.email)
        if existing_user and existing_user.id != user.id:
            raise HTTPException(
                status_code=422, detail="Email already registered")

    # Обновляем информацию пользователя
    updated_user = crud.edit_user(db, user_uuid, form_data)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")

    logger.log_message(f"User {user.email} has been updated.")

    return {
        "detail": "User successfully updated",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        }
    }

# Пример маршрута для удаления пользователя с проверкой токена через HTTPBearer


@router.delete("/users/delete/{user_id}", responses={
    200: {"description": "User successfully deleted", "content": {"application/json": {"example": {"detail": "User successfully deleted"}}}},
    400: {"description": "Bad Request - User ID is required", "content": {"application/json": {"example": {"detail": "User ID is required"}}}},
    403: {"description": "Insufficient rights or attempt to delete own account", "content": {"application/json": {"example": {"detail": "Insufficient rights"}}}},
    404: {"description": "User not found", "content": {"application/json": {"example": {"detail": "User not found"}}}},
    422: {"description": "Invalid UUID format", "content": {"application/json": {"example": {"detail": "Invalid UUID format"}}}},
}, tags=["Admin"], summary="Delete user")
def delete_user(user_id: str,
                db: Session = Depends(get_session_local),
                requesting_user: User = Depends(require_admin)):

    # Проверка, что user_id не пустой
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="User ID is required")

    # Проверка корректности UUID
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    # Проверяем, пытается ли супер-админ удалить свой собственный аккаунт
    if str(requesting_user.id) == user_id:
        raise HTTPException(
            status_code=403, detail="Super admin cannot delete own account")

    # Удаление пользователя
    user_to_delete = crud.get_user_by_id(db, user_uuid)
    if user_to_delete and user_to_delete.role == "admin" and crud.count_users_by_role(db, "admin") <= 1:
        raise HTTPException(
            status_code=403, detail="Cannot delete the last admin")

    user = crud.delete_user(db, user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    logger.log_message(
        f"Admin {requesting_user.email} deleted user {user.email}.")
    return {"detail": "User successfully deleted"}


@router.get("/get-pending-products/", tags=["Approval"], summary="Get list of products pending approval")
def get_pending_products(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(database.get_session_local),
    requesting_user: User = Depends(require_operator),
):
    token = credentials.credentials

    products_data = []

    # Получение списка продуктов из Redis
    pending_product_ids = redis_client.smembers("pending_products")
    logger.log_message(f"""Pending product IDs retrieved from Redis: {
                       pending_product_ids}""")

    for product_id in pending_product_ids:
        product_id = product_id.decode('utf-8')
        try:
            response = requests.get(
                f"http://products_service:8000/products/{product_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                timeout=5
            )
            logger.log_message(f"""Making request to http://products_service:8000/products/{
                               product_id} with headers: {{'Authorization': 'Bearer {token}', 'Content-Type': 'application/json'}}""")
            if response.status_code == 200:
                products_data.append(response.json())
            else:
                logger.log_message(f"""Failed to fetch product data for ID {
                                   product_id}: {response.status_code}""")
        except requests.RequestException as e:
            logger.log_message(f"""Error fetching product data for ID {
                               product_id}: {e}""")

    return products_data


@router.get("/user_name/{user_id}", tags=["Chat"], summary="Get user display name")
def get_user_name(user_id: uuid.UUID, db: Session = Depends(database.get_session_local)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"name": user.name}
