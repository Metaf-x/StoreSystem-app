# main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from app import database, logger, routes
from app.kafka import start_consumer
from app.graphql import schema
from app.database import init_db, SessionLocal

app = FastAPI(
    title="Order Management Microservice API",
    description="API для управления заказами в системе",
    version="1.0.0"
)

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Или укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    start_consumer()
    logger.log_message(
        "DB order_service и Kafka consumer initialized successfully")


# Функция для получения контекста
async def get_context(request: Request):
    # Создаем объект сессии
    db_session = SessionLocal()
    # Возвращаем её вместе с request
    return {
        "request": request,
        "db": db_session
    }

# Создаем GraphQL-приложение
graphql_app = GraphQLRouter(schema, context_getter=get_context)

# Добавляем маршруты для GraphQL-приложения
app.include_router(graphql_app, prefix="/graphql")
app.include_router(routes.router)
