from collections.abc import Callable, Generator
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.ai_training_plan_service import ai_training_plan_service
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


def seed_exercises(session_factory: SessionFactory, count: int = 5) -> list[Exercise]:
    db = session_factory()
    try:
        exercises = [Exercise(name=f"Exercise {index}", difficulty="beginner", is_global=True) for index in range(1, count + 1)]
        db.add_all(exercises)
        db.commit()
        for exercise in exercises:
            db.refresh(exercise)
        return exercises
    finally:
        db.close()


def plan_payload(**overrides) -> dict:
    return {
        "goal": "hypertrophy",
        "level": "beginner",
        "days_per_week": 3,
        "session_duration_minutes": 60,
        "available_equipment": [],
        "physical_limitations": None,
        "sensitive_data_acknowledged": False,
        "priorities": ["upper body"],
        **overrides,
    }


def ollama_plan_response(exercises: list[Exercise], *, explanation: str = "Plan creado por Ollama", days: int = 3) -> bytes:
    routines = []
    for day in range(1, days + 1):
        selected = [exercises[(day - 1) % len(exercises)], exercises[day % len(exercises)]]
        routines.append(
            {
                "day": day,
                "name": f"Dia IA {day}",
                "focus": "full_body",
                "description": "Sesion generada por IA.",
                "exercises": [
                    {
                        "exercise_id": str(exercise.id),
                        "exercise_name": exercise.name,
                        "target_sets": 2,
                        "target_reps_min": 8,
                        "target_reps_max": 12,
                        "target_rpe": "7",
                        "target_rir": 3,
                        "rest_seconds": 90,
                        "reason": "Seleccionado por la IA para equilibrar la sesion.",
                    }
                    for exercise in selected
                ],
            }
        )
    payload = {
        "routines": routines,
        "progression": "Progresa cuando completes el rango con buena tecnica.",
        "explanation": explanation,
        "risk_notes": "Riesgo enriquecido",
        "confidence": "high",
    }
    return json.dumps({"response": json.dumps(payload)}).encode("utf-8")


def test_generate_training_plan_creates_draft_with_one_routine_per_day(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "draft"
    assert data["days_per_week"] == 3
    assert len(data["plan_payload"]["routines"]) == 3
    assert data["provider"] == "internal"
    assert data["model"] == "rules"
    assert data["fallback_used"] is False
    assert data["input_summary"]["privacy"]["notes_included"] is False
    assert data["input_summary"]["privacy"]["physical_limitations_included"] is False
    assert data["input_summary"]["ai_provider"] == {
        "provider": "internal",
        "model": "rules",
        "external_data_sent": False,
        "fallback_used": False,
    }


def test_internal_training_plan_does_not_repeat_same_exercises_every_day(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory, count=8)
    token = register_and_login(client, "varied@example.com", "varied_user")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=4),
    )

    assert response.status_code == 201
    routines = response.json()["plan_payload"]["routines"]
    exercise_sets = [tuple(exercise["exercise_id"] for exercise in routine["exercises"]) for routine in routines]
    assert len(set(exercise_sets)) > 1


def test_generate_training_plan_requires_acknowledgement_for_physical_limitations(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(physical_limitations="Molestia de rodilla", sensitive_data_acknowledged=False),
    )

    assert response.status_code == 422


def test_generate_training_plan_accepts_acknowledged_limitations_without_leaking_to_payload(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(physical_limitations="  Molestia de rodilla  ", sensitive_data_acknowledged=True),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["physical_limitations"] == "Molestia de rodilla"
    assert data["sensitive_data_acknowledged"] is True
    assert data["input_summary"]["privacy"]["physical_limitations_included"] is True
    assert data["input_summary"]["privacy"]["notes_included"] is False
    assert "Molestia de rodilla" not in json.dumps(data["plan_payload"])
    assert "Molestia de rodilla" not in json.dumps(data["input_summary"])
    assert "email" not in data["input_summary"]
    assert "username" not in data["input_summary"]
    assert "token" not in json.dumps(data["input_summary"]).lower()


def test_generate_training_plan_treats_blank_limitations_as_absent(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(physical_limitations="   ", sensitive_data_acknowledged=False),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["physical_limitations"] is None
    assert data["input_summary"]["privacy"]["physical_limitations_included"] is False


def test_ollama_provider_generates_training_plan_structure(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    response_body = b""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def read(self):
            return response_body

    captured_body = {}

    def fake_urlopen(request, timeout):
        captured_body["body"] = request.data.decode("utf-8")
        captured_body["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    monkeypatch.setenv("APP_AI_OLLAMA_MODEL", "llama3.2")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", fake_urlopen)
    client, session_factory = client_with_db
    exercises = seed_exercises(session_factory)
    response_body = ollama_plan_response(exercises, explanation="Plan estructurado por Ollama")
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(physical_limitations="Molestia privada de rodilla", sensitive_data_acknowledged=True),
    )

    get_settings.cache_clear()
    assert response.status_code == 201
    data = response.json()
    assert data["explanation"] == "Plan estructurado por Ollama"
    assert data["risk_notes"] == "Riesgo enriquecido"
    assert data["confidence"] == "high"
    assert data["provider"] == "ollama"
    assert data["model"] == "llama3.2"
    assert data["fallback_used"] is False
    assert len(data["plan_payload"]["routines"]) == 3
    assert data["plan_payload"]["routines"][0]["name"] == "Dia IA 1"
    assert data["input_summary"]["ai_provider"]["provider"] == "ollama"
    assert data["input_summary"]["ai_provider"]["fallback_used"] is False
    assert "Molestia privada de rodilla" in captured_body["body"]
    assert "sin limitarte a una base de datos" in captured_body["body"]
    assert "plan_payload v3" in captured_body["body"]
    assert "owner@example.com" not in captured_body["body"]


def test_groq_provider_generates_training_plan_structure(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    response_body = b""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def read(self):
            return response_body

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = request.data.decode("utf-8")
        captured["authorization"] = request.get_header("Authorization")
        captured["accept"] = request.get_header("Accept")
        captured["user_agent"] = request.get_header("User-agent")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("APP_AI_PROVIDER", "groq")
    monkeypatch.setenv("APP_AI_GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("APP_AI_GROQ_MODEL", "llama-3.3-70b-versatile")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", fake_urlopen)
    client, session_factory = client_with_db
    exercises = seed_exercises(session_factory)
    groq_content = json.loads(ollama_plan_response(exercises, explanation="Plan estructurado por Groq").decode("utf-8"))["response"]
    response_body = json.dumps({"choices": [{"message": {"content": groq_content}}]}).encode("utf-8")
    token = register_and_login(client, "groq-owner@example.com", "groq_owner")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=3),
    )

    get_settings.cache_clear()
    assert response.status_code == 201
    data = response.json()
    assert data["explanation"] == "Plan estructurado por Groq"
    assert data["provider"] == "groq"
    assert data["model"] == "llama-3.3-70b-versatile"
    assert data["input_summary"]["ai_provider"]["external_data_sent"] is True
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-groq-key"
    assert captured["accept"] == "application/json"
    assert captured["user_agent"] == "ZenithCoach/1.0"
    assert "response_format" in captured["body"]
    assert "groq-owner@example.com" not in captured["body"]


def test_ollama_provider_falls_back_for_training_plan_on_invalid_response(
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
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=2),
    )

    get_settings.cache_clear()
    assert response.status_code == 201
    data = response.json()
    assert data["explanation"] == "Plan adaptativo de 2 dias para objetivo hypertrophy, nivel beginner y sesiones de 60 minutos."
    assert data["provider"] == "ollama"
    assert data["fallback_used"] is True
    assert data["input_summary"]["ai_provider"]["fallback_used"] is True


def test_generate_training_plan_rejects_invalid_internal_payload(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    monkeypatch.setattr(ai_training_plan_service, "_build_plan_payload", lambda _data, _exercises: {"version": 1, "routines": []})

    response = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=2),
    )

    assert response.status_code == 422


def test_accept_training_plan_creates_real_routines(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    plan = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=2),
    ).json()

    response = client.post(
        f"/ai/training-plans/{plan['id']}/accept",
        headers={"Authorization": f"Bearer {token}"},
    )
    routines_response = client.get("/routines", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    accepted = response.json()
    assert accepted["status"] == "accepted"
    assert len(accepted["plan_payload"]["created_routine_ids"]) == 2
    routines = routines_response.json()
    assert len(routines) == 2
    assert all(routine["exercises"] for routine in routines)


def test_accept_training_plan_does_not_copy_limitations_to_routines(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    plan = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=1, physical_limitations="Molestia de rodilla", sensitive_data_acknowledged=True),
    ).json()

    client.post(
        f"/ai/training-plans/{plan['id']}/accept",
        headers={"Authorization": f"Bearer {token}"},
    )
    routines_response = client.get("/routines", headers={"Authorization": f"Bearer {token}"})

    assert routines_response.status_code == 200
    assert "Molestia de rodilla" not in json.dumps(routines_response.json())


def test_reject_training_plan_does_not_create_routines(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    plan = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=2),
    ).json()

    response = client.post(
        f"/ai/training-plans/{plan['id']}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    routines_response = client.get("/routines", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert routines_response.json() == []


def test_modify_training_plan_creates_new_draft_and_keeps_original(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    original = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=3),
    ).json()

    response = client.post(
        f"/ai/training-plans/{original['id']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json={"instruction": "Cambialo a 4 dias y con menos volumen", "sensitive_data_acknowledged": False},
    )
    plans_response = client.get("/ai/training-plans", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    modified = response.json()
    assert modified["id"] != original["id"]
    assert modified["status"] == "draft"
    assert modified["days_per_week"] == 4
    assert len(modified["plan_payload"]["routines"]) == 4
    assert modified["input_summary"]["modified_from_plan_id"] == original["id"]
    assert modified["input_summary"]["modification_instruction"] == "Cambialo a 4 dias y con menos volumen"
    original_sets = original["plan_payload"]["routines"][0]["exercises"][0]["target_sets"]
    modified_sets = modified["plan_payload"]["routines"][0]["exercises"][0]["target_sets"]
    assert modified_sets == original_sets - 1
    plans_by_id = {plan["id"]: plan for plan in plans_response.json()}
    assert plans_by_id[original["id"]]["status"] == "draft"
    assert plans_by_id[original["id"]]["days_per_week"] == 3


def test_modify_training_plan_uses_configured_provider(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    response_body = b""

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def read(self):
            return response_body

    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", lambda _request, timeout: FakeResponse())
    client, session_factory = client_with_db
    exercises = seed_exercises(session_factory)
    response_body = ollama_plan_response(exercises, explanation="Version ajustada por Ollama")
    token = register_and_login(client, "owner@example.com", "owner_user")
    original = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=3),
    ).json()

    response = client.post(
        f"/ai/training-plans/{original['id']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json={"instruction": "Hazlo mas corto", "sensitive_data_acknowledged": False},
    )

    get_settings.cache_clear()
    assert response.status_code == 201
    modified = response.json()
    assert modified["explanation"] == "Version ajustada por Ollama"
    assert modified["provider"] == "ollama"
    assert modified["fallback_used"] is False
    assert modified["input_summary"]["modified_from_plan_id"] == original["id"]
    assert modified["input_summary"]["ai_provider"]["provider"] == "ollama"


def test_modify_training_plan_does_not_create_routines_until_accepted(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    original = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=2),
    ).json()

    modified = client.post(
        f"/ai/training-plans/{original['id']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json={"instruction": "Hazlo mas corto", "sensitive_data_acknowledged": False},
    ).json()
    routines_before_accept = client.get("/routines", headers={"Authorization": f"Bearer {token}"})
    accepted = client.post(
        f"/ai/training-plans/{modified['id']}/accept",
        headers={"Authorization": f"Bearer {token}"},
    )
    routines_after_accept = client.get("/routines", headers={"Authorization": f"Bearer {token}"})

    assert routines_before_accept.json() == []
    assert accepted.status_code == 200
    assert len(routines_after_accept.json()) == 2


def test_modify_training_plan_rejects_accepted_plan(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    plan = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(days_per_week=2),
    ).json()
    client.post(f"/ai/training-plans/{plan['id']}/accept", headers={"Authorization": f"Bearer {token}"})

    response = client.post(
        f"/ai/training-plans/{plan['id']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json={"instruction": "Hazlo mas corto", "sensitive_data_acknowledged": False},
    )

    assert response.status_code == 409


def test_other_user_cannot_modify_training_plan(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    plan = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=plan_payload(),
    ).json()

    response = client.post(
        f"/ai/training-plans/{plan['id']}/modify",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"instruction": "Hazlo mas corto", "sensitive_data_acknowledged": False},
    )

    assert response.status_code == 404


def test_modify_training_plan_requires_acknowledgement_for_sensitive_instruction(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    plan = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {token}"},
        json=plan_payload(),
    ).json()

    response = client.post(
        f"/ai/training-plans/{plan['id']}/modify",
        headers={"Authorization": f"Bearer {token}"},
        json={"instruction": "Evita ejercicios por dolor de rodilla", "sensitive_data_acknowledged": False},
    )

    assert response.status_code == 422


def test_other_user_cannot_read_training_plan(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    plan = client.post(
        "/ai/training-plans/generate",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=plan_payload(),
    ).json()

    response = client.get(f"/ai/training-plans/{plan['id']}", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 404
