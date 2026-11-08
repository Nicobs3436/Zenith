import json
from collections.abc import Callable, Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.exercise import Exercise
from app.infrastructure.db.session import get_db
from app.main import app

SessionFactory = Callable[[], Session]


@pytest.fixture()
def client_with_db() -> Generator[tuple[TestClient, SessionFactory], None, None]:
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
            yield test_client, testing_session_local
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def register_and_login(client: TestClient, email: str, username: str) -> str:
    password = "password123"
    client.post("/auth/register", json={"email": email, "username": username, "password": password})
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def seed_global_exercise(session_factory: SessionFactory, name: str = "Squat") -> Exercise:
    db = session_factory()
    try:
        exercise = Exercise(name=name, difficulty="beginner", is_global=True)
        db.add(exercise)
        db.commit()
        db.refresh(exercise)
        return exercise
    finally:
        db.close()


def create_session(client: TestClient, token: str, exercise_id: str, *, unit: str = "kg") -> dict:
    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 8, 10, 0, tzinfo=UTC).isoformat(),
            "finished_at": datetime(2026, 7, 8, 11, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "notes": "private session note",
            "sets": [
                {
                    "exercise_id": exercise_id,
                    "set_number": 1,
                    "reps": 10,
                    "weight_value": "100",
                    "weight_unit": unit,
                    "rpe": "9",
                    "rir": 0,
                    "rest_seconds": 90,
                    "notes": "private set note",
                },
                {
                    "exercise_id": exercise_id,
                    "set_number": 2,
                    "reps": 7,
                    "weight_value": "100",
                    "weight_unit": unit,
                    "rpe": "9",
                    "rir": 0,
                    "rest_seconds": 90,
                },
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_generate_session_summary_returns_metrics_without_notes(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(client, token, str(exercise.id))

    response = client.post(
        f"/ai/session-summaries/{session['id']}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["session_id"] == session["id"]
    assert data["provider"] == "internal"
    assert data["fallback_used"] is False
    assert data["input_summary"]["privacy"] == {
        "notes_included": False,
        "email_included": False,
        "username_included": False,
        "tokens_included": False,
    }
    assert data["input_summary"]["totals"]["volume_by_unit"] == {"kg": "1700.00"}
    assert data["drops"] == ["Squat bajo de 10 a 7 reps entre series."]
    assert "RPE promedio alto" in data["warnings"][0]
    serialized = json.dumps(data)
    assert "private session note" not in serialized
    assert "private set note" not in serialized
    assert "owner@example.com" not in serialized


def test_get_session_summary_returns_generated_summary(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(client, token, str(exercise.id))
    generated = client.post(
        f"/ai/session-summaries/{session['id']}/generate",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    response = client.get(f"/ai/session-summaries/{session['id']}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == generated["id"]


def test_other_user_cannot_generate_or_read_session_summary(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    session = create_session(client, owner_token, str(exercise.id))

    generate_response = client.post(
        f"/ai/session-summaries/{session['id']}/generate",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    get_response = client.get(
        f"/ai/session-summaries/{session['id']}", headers={"Authorization": f"Bearer {other_token}"}
    )

    assert generate_response.status_code == 404
    assert get_response.status_code == 404


def test_deleted_session_cannot_generate_summary(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(client, token, str(exercise.id))
    client.delete(f"/workout-sessions/{session['id']}", headers={"Authorization": f"Bearer {token}"})

    response = client.post(
        f"/ai/session-summaries/{session['id']}/generate",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_regenerate_session_summary_updates_existing_row(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(client, token, str(exercise.id))

    first = client.post(
        f"/ai/session-summaries/{session['id']}/generate", headers={"Authorization": f"Bearer {token}"}
    ).json()
    second = client.post(
        f"/ai/session-summaries/{session['id']}/generate", headers={"Authorization": f"Bearer {token}"}
    ).json()

    assert second["id"] == first["id"]


def test_session_summary_keeps_kg_and_lb_volumes_separate(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 8, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [
                {
                    "exercise_id": str(exercise.id),
                    "set_number": 1,
                    "reps": 10,
                    "weight_value": "50",
                    "weight_unit": "kg",
                },
                {
                    "exercise_id": str(exercise.id),
                    "set_number": 2,
                    "reps": 10,
                    "weight_value": "100",
                    "weight_unit": "lb",
                },
            ],
        },
    ).json()

    response = client.post(
        f"/ai/session-summaries/{session['id']}/generate", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["input_summary"]["totals"]["volume_by_unit"] == {"kg": "500.00", "lb": "1000.00"}
    assert any("kg y lb" in warning for warning in data["warnings"])


def test_ollama_enriches_session_summary_without_notes(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def read(self):
            return (
                b'{"response": "{\\"summary\\": \\"Resumen Ollama\\", '
                b'\\"improvements\\": [\\"Mejora Ollama\\"], '
                b'\\"drops\\": [], '
                b'\\"warnings\\": [\\"Warning Ollama\\"], '
                b'\\"next_recommendation\\": \\"Siguiente Ollama\\"}"}'
            )

    captured_body = {}

    def fake_urlopen(request, timeout):
        captured_body["body"] = request.data.decode("utf-8")
        return FakeResponse()

    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", fake_urlopen)
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(client, token, str(exercise.id))

    response = client.post(
        f"/ai/session-summaries/{session['id']}/generate", headers={"Authorization": f"Bearer {token}"}
    )

    get_settings.cache_clear()
    assert response.status_code == 201
    data = response.json()
    assert data["summary"] == "Resumen Ollama"
    assert data["improvements"] == ["Mejora Ollama"]
    assert data["warnings"] == ["Warning Ollama"]
    assert data["next_recommendation"] == "Siguiente Ollama"
    assert data["provider"] == "ollama"
    assert data["fallback_used"] is False
    assert "private session note" not in captured_body["body"]
    assert "private set note" not in captured_body["body"]


def test_ollama_session_summary_falls_back_on_invalid_response(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def read(self):
            return b'{"response": "not json"}'

    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", lambda _request, timeout: FakeResponse())
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(client, token, str(exercise.id))

    response = client.post(
        f"/ai/session-summaries/{session['id']}/generate", headers={"Authorization": f"Bearer {token}"}
    )

    get_settings.cache_clear()
    assert response.status_code == 201
    data = response.json()
    assert data["provider"] == "ollama"
    assert data["fallback_used"] is True
    assert data["summary"].startswith("Sesion con")
