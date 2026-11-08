import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.test_auth import client, user_payload  # noqa: F401  fixture de pytest

PASSWORD = "password123"


@pytest.fixture()
def outbox(monkeypatch) -> list:
    sent: list = []
    monkeypatch.setattr("app.api.auth.send_email_safely", lambda email: sent.append(email))
    return sent


def token_from(email) -> str:
    match = re.search(r"token=([\w\-]+)", email.text)
    assert match, email.text
    return match.group(1)


def test_register_requires_terms_and_adult_confirmation(client: TestClient) -> None:
    for missing in ("accepted_terms", "adult_confirmed"):
        payload = user_payload()
        payload.pop(missing)
        assert client.post("/auth/register", json=payload).status_code == 422
    payload = user_payload()
    payload["adult_confirmed"] = False
    assert client.post("/auth/register", json=payload).status_code == 422


def test_register_sends_verification_email_and_verify_marks_user(client: TestClient, outbox: list) -> None:
    created = client.post("/auth/register", json=user_payload())
    assert created.status_code == 201
    assert created.json()["email_verified"] is False
    assert len(outbox) == 1 and outbox[0].to == "test@example.com"

    token = token_from(outbox[0])
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 204
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400

    login = client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD}).json()
    me = client.get("/users/me", headers={"Authorization": f"Bearer {login['access_token']}"}).json()
    assert me["email_verified"] is True


def test_password_reset_flow(client: TestClient, outbox: list) -> None:
    client.post("/auth/register", json=user_payload())
    old_session = client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD}).json()
    outbox.clear()

    unknown = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})
    known = client.post("/auth/password-reset/request", json={"email": "TEST@example.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(outbox) == 1

    token = token_from(outbox[0])
    bad = client.post(
        "/auth/password-reset/confirm", json={"token": "not-a-valid-token", "new_password": "new-password-1"}
    )
    assert bad.status_code == 400
    ok = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "new-password-1"})
    assert ok.status_code == 204
    reused = client.post("/auth/password-reset/confirm", json={"token": token, "new_password": "other-password"})
    assert reused.status_code == 400

    assert client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD}).status_code == 401
    assert (
        client.post("/auth/login", json={"email": "test@example.com", "password": "new-password-1"}).status_code == 200
    )
    # Las sesiones anteriores quedan cerradas.
    assert client.post("/auth/refresh", json={"refresh_token": old_session["refresh_token"]}).status_code == 401


def test_web_client_gets_refresh_token_only_as_httponly_cookie(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("APP_REFRESH_COOKIE_SECURE", "false")
    get_settings.cache_clear()
    web = {"X-Zenith-Client": "web"}
    client.post("/auth/register", json=user_payload())

    login = client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD}, headers=web)
    assert login.status_code == 200
    assert login.json()["refresh_token"] is None
    set_cookie = login.headers["set-cookie"].lower()
    assert "zenith_refresh=" in set_cookie and "httponly" in set_cookie and "samesite=strict" in set_cookie

    # Sin la cabecera de la web, la cookie se ignora (proteccion CSRF).
    assert client.post("/auth/refresh").status_code == 401
    refreshed = client.post("/auth/refresh", headers=web)
    assert refreshed.status_code == 200 and refreshed.json()["refresh_token"] is None

    assert client.post("/auth/logout", headers=web).status_code == 204
    assert client.post("/auth/refresh", headers=web).status_code == 401
    get_settings.cache_clear()


def test_mobile_client_still_receives_refresh_token(client: TestClient) -> None:
    client.post("/auth/register", json=user_payload())
    login = client.post("/auth/login", json={"email": "test@example.com", "password": PASSWORD}).json()
    assert login["refresh_token"]
