from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
from app.infrastructure.db.session import get_db
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def user_payload(email: str = "test@example.com", username: str = "test_user") -> dict[str, str]:
    return {"email": email, "username": username, "password": "password123"}


def test_register_user_returns_created_user_without_password_hash(client: TestClient) -> None:
    response = client.post("/auth/register", json=user_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "test_user"
    assert data["is_active"] is True
    assert "id" in data
    assert "password_hash" not in data


def test_register_user_rejects_duplicate_email(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())

    response = client.post(
        "/auth/register",
        json=user_payload(email="test@example.com", username="another_user"),
    )

    assert response.status_code == 409


def test_login_returns_access_token(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())

    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]


def test_refresh_returns_new_token_pair_and_rotates_refresh_token(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    old_refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})

    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != old_refresh_token

    reused_response = client.post("/auth/refresh", json={"refresh_token": old_refresh_token})
    assert reused_response.status_code == 401


def test_refreshed_access_token_can_read_current_user(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )

    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": login_response.json()["refresh_token"]},
    )
    access_token = refresh_response.json()["access_token"]

    response = client.get("/users/me", headers={"Authorization": f"Bearer {access_token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_refresh_rejects_invalid_token(client: TestClient) -> None:
    response = client.post("/auth/refresh", json={"refresh_token": "invalid-token"})

    assert response.status_code == 401


def test_refresh_rejects_expired_token(client: TestClient) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    original_days = settings.refresh_token_expire_days
    settings.refresh_token_expire_days = -1
    try:
        client.post("/auth/register", json=user_payload())
        login_response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
    finally:
        settings.refresh_token_expire_days = original_days

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login_response.json()["refresh_token"]},
    )

    assert response.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post("/auth/logout", json={"refresh_token": refresh_token})
    refresh_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert logout_response.status_code == 204
    assert refresh_response.status_code == 401


def test_login_rejects_invalid_password(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())

    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_rate_limit_blocks_repeated_attempts(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 429


def test_register_rate_limit_blocks_repeated_attempts(client: TestClient) -> None:
    for index in range(5):
        response = client.post(
            "/auth/register",
            json=user_payload(email=f"test{index}@example.com", username=f"test_user_{index}"),
        )
        assert response.status_code == 201

    response = client.post(
        "/auth/register",
        json=user_payload(email="blocked@example.com", username="blocked_user"),
    )

    assert response.status_code == 429


def test_users_me_returns_current_user_with_valid_token(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())
    login_response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


def test_users_me_requires_token(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 401


def test_email_is_case_insensitive_for_register_and_login(client: TestClient) -> None:
    created = client.post("/auth/register", json=user_payload(email="Juan.Perez@Example.com", username="juan"))
    duplicate = client.post("/auth/register", json=user_payload(email="juan.perez@example.com", username="juan2"))
    login = client.post("/auth/login", json={"email": "JUAN.PEREZ@example.com", "password": user_payload()["password"]})

    assert created.status_code == 201
    assert created.json()["email"] == "juan.perez@example.com"
    assert duplicate.status_code == 409
    assert login.status_code == 200
