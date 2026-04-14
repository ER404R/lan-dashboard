"""Pytest configuration and shared fixtures for lan-dashboard tests.

IMPORTANT: env vars must be set BEFORE any app module is imported so that
Settings() picks them up at construction time.
"""
import os
import re

# ---------------------------------------------------------------------------
# Override environment BEFORE app modules are imported
# ---------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REGISTRATION_ENABLED", "true")
os.environ.setdefault("ADMIN_INVITE_TOKEN", "admin-test-token-999")
os.environ.setdefault("SEED_INVITE_TOKENS", "")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Test engine - single in-memory SQLite shared across sessions via StaticPool
# ---------------------------------------------------------------------------
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)

# ---------------------------------------------------------------------------
# Patch app.database BEFORE importing app.main so that when app.main does
# "from app.database import SessionLocal" it gets our test session factory.
# ---------------------------------------------------------------------------
import app.database as _app_db

_app_db.engine = _test_engine
_app_db.SessionLocal = _TestingSession

# Now safe to import the rest of the app
from app.auth import hash_password
from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import FeatureRequest, Game, InviteToken, Score, User

# ---------------------------------------------------------------------------
# Override get_db so every route handler also uses the test session factory
# ---------------------------------------------------------------------------
def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db




# ---------------------------------------------------------------------------
# Auto-use fixture: recreate schema for every test.
# Client fixtures must explicitly depend on this to guarantee ordering.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean_db():
    # Reset rate limiter storage so per-IP counters don't bleed across tests
    from app.limiter import limiter as _limiter
    _limiter.reset()
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    yield


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def db(_clean_db):
    """Direct DB session for fixture helpers / assertions."""
    session = _TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(_clean_db):
    """Unauthenticated TestClient.
    Explicitly depends on _clean_db so tables exist before the lifespan runs."""
    with TestClient(app, raise_server_exceptions=True, base_url="https://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
def create_user(db, username="testuser", password="testpass1!", is_admin=False):
    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_invite_token(db, token="invite-token-abc", max_uses=5, revoked=False):
    it = InviteToken(token=token, max_uses=max_uses, revoked=revoked)
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


def create_game(db, name="Test Game", added_by_id=None, steam_appid=None):
    if added_by_id is None:
        u = User(username="gameowner", password_hash=hash_password("password1!"))
        db.add(u)
        db.flush()
        added_by_id = u.id
    game = Game(name=name, added_by_id=added_by_id, steam_appid=steam_appid)
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


# ---------------------------------------------------------------------------
# Helper: extract CSRF token from rendered HTML
# ---------------------------------------------------------------------------
def extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Authenticated client fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def auth_client(client, db):
    user = create_user(db)
    resp = client.get("/login")
    csrf = extract_csrf(resp.text)
    client.post(
        "/login",
        data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
        follow_redirects=False,
    )
    return client, user


@pytest.fixture()
def admin_client(client, db):
    admin = create_user(db, username="adminuser", password="adminpass1!", is_admin=True)
    resp = client.get("/login")
    csrf = extract_csrf(resp.text)
    client.post(
        "/login",
        data={"username": "adminuser", "password": "adminpass1!", "csrf_token": csrf},
        follow_redirects=False,
    )
    return client, admin
