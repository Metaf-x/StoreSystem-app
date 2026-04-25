# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app import routes, database, logger, auth
from app.kafka import start_consumer
from fastapi.staticfiles import StaticFiles
import os


app = FastAPI(
    title="Warehouse Management Microservice API",
    description="API for managing products and suppliers in the warehouse",
    version="1.0.0"
)
# Добавляем схему безопасности OAuth2 с токенами
security = HTTPBearer()

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:8001,http://127.0.0.1:8001"
)


def _cors_origins():
    return [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/img", StaticFiles(directory="img"), name="img")


@app.on_event("startup")
def startup():
    database.init_db()
    start_consumer()
    logger.log_message("Database initialized.")


app.include_router(routes.router)


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
