import os


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "2a0b1357b8ca70b0446034e6cbe68e5810f2acd7ec10a98b83cd109bd0b12262",
)
SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL",
    "postgresql://storage_admin:THw7l0bxvPPkWUhP@db_auth:5432/strg_users_db",
)

SEED_SUPERADMIN_ENABLED = os.getenv(
    "SEED_SUPERADMIN_ENABLED",
    "true",
).lower() not in {"0", "false", "no", "off"}
SEED_SUPERADMIN_NAME = os.getenv("SEED_SUPERADMIN_NAME", "Super Admin")
SEED_SUPERADMIN_EMAIL = os.getenv("SEED_SUPERADMIN_EMAIL", "admin@example.com")
SEED_SUPERADMIN_PASSWORD = os.getenv("SEED_SUPERADMIN_PASSWORD", "Admin12345")
