from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "auth_service"))

from app import crud, database
from app.schemas import UserCreate


class _FakeCursor:
    def execute(self, *args, **kwargs):
        return None

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class _FakeRawConnection:
    def cursor(self):
        return _FakeCursor()


class _FakeConnection:
    connection = _FakeRawConnection()


class _FakeDb:
    def __init__(self):
        self.added = None
        self.commit_count = 0
        self.refresh_count = 0
        self.closed = False

    def connection(self):
        return _FakeConnection()

    def add(self, value):
        self.added = value

    def commit(self):
        self.commit_count += 1

    def refresh(self, value):
        self.refresh_count += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class _ExistingUser:
    def __init__(self, role="customer", is_superadmin=False):
        self.role = role
        self.is_superadmin = is_superadmin


class CreateUserTest(unittest.TestCase):
    def test_create_user_persists_admin_role(self):
        db = _FakeDb()
        user = UserCreate(
            name="Super Admin",
            email="admin@example.com",
            password="Admin12345",
        )

        crud.create_user(db=db, user=user, is_superadmin=True)

        self.assertIsNotNone(db.added)
        self.assertEqual(db.added.role, "admin")
        self.assertTrue(db.added.is_superadmin)
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(db.refresh_count, 1)


class SeedSuperadminTest(unittest.TestCase):
    def test_seed_superadmin_creates_missing_user(self):
        db = _FakeDb()
        created_user = object()

        with patch.object(database, "SessionLocal", return_value=db), \
                patch.object(database, "SEED_SUPERADMIN_ENABLED", True), \
                patch.object(database, "SEED_SUPERADMIN_NAME", "Super Admin"), \
                patch.object(database, "SEED_SUPERADMIN_EMAIL", "ADMIN@example.com"), \
                patch.object(database, "SEED_SUPERADMIN_PASSWORD", "Admin12345"), \
                patch.object(database.crud, "get_user_by_email", return_value=None) as get_user, \
                patch.object(database.crud, "create_user", return_value=created_user) as create_user:
            result = database.seed_superadmin()

        self.assertIs(result, created_user)
        get_user.assert_called_once_with(db, "admin@example.com")
        create_user.assert_called_once()
        self.assertEqual(create_user.call_args.kwargs["role"], "admin")
        self.assertEqual(create_user.call_args.kwargs["user"].email, "admin@example.com")
        self.assertTrue(db.closed)

    def test_seed_superadmin_promotes_existing_seed_user(self):
        db = _FakeDb()
        existing_user = _ExistingUser(role="customer", is_superadmin=False)

        with patch.object(database, "SessionLocal", return_value=db), \
                patch.object(database, "SEED_SUPERADMIN_ENABLED", True), \
                patch.object(database, "SEED_SUPERADMIN_EMAIL", "admin@example.com"), \
                patch.object(database.crud, "get_user_by_email", return_value=existing_user), \
                patch.object(database.crud, "create_user") as create_user:
            result = database.seed_superadmin()

        self.assertIs(result, existing_user)
        self.assertEqual(existing_user.role, "admin")
        self.assertTrue(existing_user.is_superadmin)
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(db.refresh_count, 1)
        create_user.assert_not_called()
        self.assertTrue(db.closed)


if __name__ == "__main__":
    unittest.main()
