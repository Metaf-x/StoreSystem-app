# main.py
from fastapi import FastAPI, Request, Depends, HTTPException, status
from datetime import datetime

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app import routes, database, logger, crud, kafka, schemas
from sqlalchemy.orm import Session
from app.models import Token, User
from app.database import get_session_local
from app.auth import verify_token
import threading
import uuid
import requests
from app.kafka import create_topic_if_not_exists

app = FastAPI(
    # Укажите название вашего микросервиса здесь
    title="User Manager Microservice API",
    # Описание вашего микросервиса
    description="API for managing users and roles in the application",
    version="1.0.0"  # Версия микросервиса
)

# Добавляем схему безопасности OAuth2 с токенами
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Либо список доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def start_kafka_consumer():
    # Запуск Kafka Consumer в отдельном потоке
    kafka_thread = threading.Thread(
        target=kafka.listen_for_product_approval_requests, daemon=True)
    kafka_thread.start()


templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def startup():
    database.init_db()
    create_topic_if_not_exists('product_topic')
    create_topic_if_not_exists('orders')
    create_topic_if_not_exists('order_responses')
    start_kafka_consumer()
    logger.log_message("Database initialized.")
    logger.log_message("Kafka consumer started.")


app.include_router(routes.router)

ROLE_ORDER = {"customer": 0, "operator": 1, "admin": 2}


def _get_current_user_from_refresh_cookie(request: Request, db: Session):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token_record = db.query(Token).filter(
        Token.refresh_token == refresh_token,
        Token.refresh_expires_at > datetime.utcnow(),
    ).first()
    if not token_record:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = db.query(User).filter(User.id == uuid.UUID(token_record.user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _require_page_role(request: Request, db: Session, minimum_role: str):
    user = _get_current_user_from_refresh_cookie(request, db)
    if ROLE_ORDER.get(user.role, -1) < ROLE_ORDER[minimum_role]:
        raise HTTPException(status_code=403, detail="Insufficient rights")
    return user

# Вспомогательная функция для рендеринга с проверкой роли супер админа


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/login", status_code=303)


@app.get("/products", response_class=HTMLResponse, include_in_schema=False)
def get_products_page(request: Request):
    return templates.TemplateResponse("products.html", {"request": request})


@app.get("/suppliers", response_class=HTMLResponse, include_in_schema=False)
def get_suppliers_page(request: Request):
    return templates.TemplateResponse("suppliers.html", {"request": request})


@app.get("/warehouses", response_class=HTMLResponse, include_in_schema=False)
def get_warehouses_page(request: Request):
    return templates.TemplateResponse("warehouses.html", {"request": request})


@app.get("/pending-approval", response_class=HTMLResponse, include_in_schema=False)
async def pending_approval_page(request: Request, db: Session = Depends(get_session_local)):
    _require_page_role(request, db, "operator")
    return templates.TemplateResponse("pending_approval.html", {"request": request})


@app.get("/user-list", response_class=HTMLResponse, include_in_schema=False)
def get_user_list(request: Request, db: Session = Depends(get_session_local)):
    _require_page_role(request, db, "admin")
    return templates.TemplateResponse("userlist.html", {"request": request})


@app.get("/orders", response_class=HTMLResponse, include_in_schema=False)
def get_user_list(request: Request):
    return templates.TemplateResponse("orders.html", {"request": request})


@app.get("/cart", response_class=HTMLResponse, include_in_schema=False)
def cart_page(request: Request):
    return templates.TemplateResponse("cart.html", {"request": request})


@app.get("/shipments", response_class=HTMLResponse, include_in_schema=False)
async def shipments_page(request: Request):
    return templates.TemplateResponse("shipments.html", {"request": request})


@app.get("/warehouses_detail/{warehouse_id}", response_class=HTMLResponse, include_in_schema=False)
def warehouse_page(
        warehouse_id: str, request: Request):

    # Передаем данные о складе и продуктах в шаблон
    return templates.TemplateResponse("product_in_warehouse.html", {
        "request": request,
        "warehouse": warehouse_id,
    })


@app.get("/chat-ui", response_class=HTMLResponse, include_in_schema=False)
def chat_ui(request: Request):
    # здесь можно какую-то логику проверить
    return templates.TemplateResponse("chats.html", {"request": request})


@app.get("/admin_orders", response_class=HTMLResponse, include_in_schema=False)
async def pending_approval_page(request: Request, db: Session = Depends(get_session_local)):
    _require_page_role(request, db, "operator")
    return templates.TemplateResponse("admin_orders.html", {"request": request})


# Обновляем OpenAPI-схему для отображения Bearer токена в Swagger UI
@app.get("/openapi.json", include_in_schema=False)
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = app.openapi()
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [
                {"bearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def _get_current_user_from_access_token(token: str, db: Session):
    payload = verify_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user, user_id


def _user_response(user: User):
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


@app.post(
    "/verify-token",
    response_model=schemas.TokenValidationResponseSchema,
    tags=["Auth"],
    summary="Verify access token",
)
async def verify_token_endpoint(
    body: schemas.TokenRequestSchema,
    db: Session = Depends(get_session_local),
):
    try:
        user, user_id = _get_current_user_from_access_token(body.token, db)
        logger.log_message(f"""Returning from verify_token_endpoint: valid=True, user_id={
                           user_id}, role={user.role}""")
        return {"valid": True, "user_id": user_id, "role": user.role}
    except HTTPException as e:
        return {"valid": False, "error": str(e.detail)}


@app.get(
    "/me",
    response_model=schemas.MeResponseSchema,
    tags=["Auth"],
    summary="Get current user",
)
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_session_local)
):
    token = credentials.credentials
    user, _ = _get_current_user_from_access_token(token, db)

    return _user_response(user)
