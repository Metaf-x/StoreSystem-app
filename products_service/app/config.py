# config.py
from pathlib import Path

SECRET_KEY = "2a0b1357b8ca70b0446034e6cbe68e5810f2acd7ec10a98b83cd109bd0b12262"
SQLALCHEMY_DATABASE_URI = "postgresql://storage_admin:THw7l0bxvPPkWUhP@db_products:5432/strg_products_db"


UPLOAD_DIR = Path("img")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPPLIER_DOCUMENTS_DIR = Path("uploads") / "supplier_documents"
SUPPLIER_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
