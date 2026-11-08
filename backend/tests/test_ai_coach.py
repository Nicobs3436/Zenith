from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.ai import AiSuggestion
from app.infrastructure.db.models.exercise import Equipment, Exercise, MuscleGroup
from app.infrastructure.db.session import get_db
from app.main import app

type SessionFactory = Callable[[], Session]


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
    client.post(
        "/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "accepted_terms": True,
            "adult_confirmed": True,
        },
    )
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def seed_global_exercise(session_factory: SessionFactory, name: str = "Bench press") -> Exercise:
    db = session_factory()
    try:
        exercise = Exercise(name=name, difficulty="beginner", is_global=True)
        db.add(exercise)
        db.commit()
        db.refresh(exercise)
        return exercise
    finally:
        db.close()


def seed_exercise_catalog(session_factory: SessionFactory) -> dict[str, Exercise]:
    db = session_factory()
    try:
        chest = MuscleGroup(name="Chest")
        legs = MuscleGroup(name="Legs")
        machine = Equipment(name="Machine")
        current = Exercise(
            name="Bench press", difficulty="beginner", is_global=True, muscle_groups=[chest], equipment=[machine]
        )
        best = Exercise(
            name="Chest press", difficulty="beginner", is_global=True, muscle_groups=[chest], equipment=[machine]
        )
        weaker = Exercise(
            name="Leg press", difficulty="beginner", is_global=True, muscle_groups=[legs], equipment=[machine]
        )
        db.add_all([chest, legs, machine, current, best, weaker])
        db.commit()
        for exercise in [current, best, weaker]:
            db.refresh(exercise)
        return {"current": current, "best": best, "weaker": weaker}
    finally:
        db.close()


def create_private_exercise(client: TestClient, token: str, name: str = "Private alternative") -> str:
    response = client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "difficulty": "beginner"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_routine(
    client: TestClient,
    token: str,
    exercise_id: str,
    *,
    target_sets: int = 3,
    target_reps_min: int = 6,
    target_reps_max: int = 8,
    rest_seconds: int = 180,
    goal: str = "Strength",
) -> dict[str, Any]:
    response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Strength plan",
            "goal": goal,
            "exercises": [
                {
                    "exercise_id": exercise_id,
                    "position": 1,
                    "target_sets": target_sets,
                    "target_reps_min": target_reps_min,
                    "target_reps_max": target_reps_max,
                    "target_rpe": "8",
                    "target_rir": 2,
                    "rest_seconds": rest_seconds,
                    "notes": "private routine note must stay local",
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def create_session(
    client: TestClient,
    token: str,
    routine_id: str,
    exercise_id: str,
    started_at: datetime,
    weight_unit: str = "kg",
    reps: int | list[int] = 8,
    weight_value: str = "50",
    rpe: str = "7",
    rir: int = 2,
    rest_seconds: int = 180,
) -> dict[str, Any]:
    reps_by_set = reps if isinstance(reps, list) else [reps, reps, reps]
    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "routine_id": routine_id,
            "started_at": started_at.isoformat(),
            "timezone": "Europe/Madrid",
            "notes": "private session note must stay local",
            "sets": [
                {
                    "exercise_id": exercise_id,
                    "set_number": set_number,
                    "reps": set_reps,
                    "weight_value": weight_value,
                    "weight_unit": weight_unit,
                    "rpe": rpe,
                    "rir": rir,
                    "rest_seconds": rest_seconds,
                    "notes": "private set note must stay local",
                }
                for set_number, set_reps in enumerate(reps_by_set, start=1)
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def setup_progression_context(
    client_with_db: tuple[TestClient, SessionFactory],
) -> tuple[TestClient, str, dict[str, Any], dict[str, Any]]:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id))
    first_session = create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    )
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 8, 10, 0, tzinfo=UTC))
    return client, token, routine, first_session


def test_generate_suggestions_tracks_inputs_without_notes(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, token, _routine, _session = setup_progression_context(client_with_db)

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    suggestion = data[0]
    assert suggestion["type"] == "increase_weight"
    assert suggestion["status"] == "pending"
    assert suggestion["input_summary"]["privacy"] == {
        "provider": "internal",
        "model": "rules",
        "external_data_sent": False,
        "notes_included": False,
    }
    assert suggestion["input_summary"]["ai_provider"] == {
        "provider": "internal",
        "model": "rules",
        "external_data_sent": False,
        "fallback_used": False,
        "prompt_summary": {
            "included_notes": False,
            "included_account_data": False,
            "included_metrics": True,
            "included_planned_change": True,
        },
    }
    assert suggestion["risk_notes"]
    assert suggestion["confidence"] == "high"
    assert suggestion["input_summary"]["rule_triggered"] == "rep_target_met_with_recovery_margin"
    assert suggestion["input_summary"]["metrics"]["avg_reps"] == "8.00"
    assert suggestion["input_summary"]["analysis_window"]["sessions_used"] == 2
    assert "private" not in str(suggestion["input_summary"])
    assert suggestion["apply_payload"]["changes"] == {"target_weight_value": "51.25", "target_weight_unit": "kg"}


def test_accept_suggestion_applies_routine_change_without_changing_sessions(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, token, routine, first_session = setup_progression_context(client_with_db)
    suggestion = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"}).json()[0]

    response = client.post(
        f"/ai/suggestions/{suggestion['id']}/accept",
        headers={"Authorization": f"Bearer {token}"},
    )
    routine_response = client.get(f"/routines/{routine['id']}", headers={"Authorization": f"Bearer {token}"})
    session_response = client.get(
        f"/workout-sessions/{first_session['id']}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    planned_exercise = routine_response.json()["exercises"][0]
    assert planned_exercise["target_weight_value"] == "51.25"
    assert planned_exercise["target_weight_unit"] == "kg"
    assert session_response.json()["sets"][0]["weight_value"] == "50.00"


def test_reject_suggestion_does_not_modify_routine(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, token, routine, _session = setup_progression_context(client_with_db)
    suggestion = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"}).json()[0]

    response = client.post(
        f"/ai/suggestions/{suggestion['id']}/reject",
        headers={"Authorization": f"Bearer {token}"},
    )
    routine_response = client.get(f"/routines/{routine['id']}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    planned_exercise = routine_response.json()["exercises"][0]
    assert planned_exercise["target_weight_value"] is None
    assert planned_exercise["target_weight_unit"] is None


def test_other_user_cannot_accept_suggestion(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, token, _routine, _session = setup_progression_context(client_with_db)
    other_token = register_and_login(client, "other@example.com", "other_user")
    suggestion = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"}).json()[0]

    response = client.post(
        f"/ai/suggestions/{suggestion['id']}/accept",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_generate_suggestions_does_not_mix_units(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id))
    create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 1, 10, 0, tzinfo=UTC), weight_unit="kg"
    )
    create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 8, 10, 0, tzinfo=UTC), weight_unit="lb"
    )

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    assert response.json() == []


def test_generate_suggestions_does_not_duplicate_pending_matches(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, token, _routine, _session = setup_progression_context(client_with_db)

    first_response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})
    second_response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})
    list_response = client.get("/ai/suggestions", headers={"Authorization": f"Bearer {token}"})

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()[0]["id"] == first_response.json()[0]["id"]
    assert [suggestion["status"] for suggestion in list_response.json()] == ["pending"]


def test_generate_suggestions_expires_obsolete_pending_suggestions(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id))
    create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 1, 10, 0, tzinfo=UTC), reps=[10, 7, 6]
    )
    create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 8, 10, 0, tzinfo=UTC), reps=[10, 7, 6]
    )
    first_response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 15, 10, 0, tzinfo=UTC), reps=[8, 8, 8]
    )
    second_response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})
    list_response = client.get("/ai/suggestions", headers={"Authorization": f"Bearer {token}"})

    assert first_response.json()[0]["type"] == "increase_rest"
    assert second_response.json() == []
    assert [suggestion["status"] for suggestion in list_response.json()] == ["expired"]


def test_generate_suggestions_can_reduce_volume(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id), target_sets=4)
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 1, 10, 0, tzinfo=UTC), rpe="7")
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 8, 10, 0, tzinfo=UTC), rpe="9")

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["type"] == "reduce_volume"
    assert suggestion["apply_payload"]["changes"] == {"target_sets": 3}
    assert suggestion["input_summary"]["rule_triggered"] == "high_effort_reduce_volume"


def test_generate_suggestions_can_recommend_deload_before_reduce_volume(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id), target_sets=3, rest_seconds=180)
    create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        reps=[10, 8, 6],
        weight_value="100",
        rpe="9",
        rir=0,
    )
    create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        reps=[10, 8, 6],
        weight_value="100",
        rpe="9",
        rir=0,
    )
    latest_session = create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
        reps=[10, 7, 5],
        weight_value="90",
        rpe="9",
        rir=0,
    )

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["type"] == "deload_recommended"
    assert suggestion["apply_payload"]["changes"] == {
        "target_sets": 2,
        "target_weight_value": "81.00",
        "target_weight_unit": "kg",
        "rest_seconds": 210,
    }
    assert suggestion["input_summary"]["rule_triggered"] == "repeated_fatigue_deload"

    accept_response = client.post(
        f"/ai/suggestions/{suggestion['id']}/accept", headers={"Authorization": f"Bearer {token}"}
    )
    routine_response = client.get(f"/routines/{routine['id']}", headers={"Authorization": f"Bearer {token}"})
    session_response = client.get(
        f"/workout-sessions/{latest_session['id']}", headers={"Authorization": f"Bearer {token}"}
    )

    assert accept_response.status_code == 200
    planned_exercise = routine_response.json()["exercises"][0]
    assert planned_exercise["target_sets"] == 2
    assert planned_exercise["target_weight_value"] == "81.00"
    assert planned_exercise["target_weight_unit"] == "kg"
    assert planned_exercise["rest_seconds"] == 210
    assert session_response.json()["sets"][0]["weight_value"] == "90.00"


def test_generate_suggestions_does_not_recommend_deload_with_mixed_recent_units(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id), target_sets=3)
    create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        weight_unit="lb",
        reps=[10, 8, 6],
        rpe="9",
        rir=0,
    )
    create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        weight_unit="kg",
        reps=[10, 8, 6],
        rpe="9",
        rir=0,
    )
    create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 15, 10, 0, tzinfo=UTC),
        weight_unit="kg",
        reps=[10, 7, 5],
        rpe="9",
        rir=0,
    )

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    assert all(suggestion["type"] != "deload_recommended" for suggestion in response.json())


def test_generate_suggestions_can_recommend_exercise_swap(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    catalog = seed_exercise_catalog(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(catalog["current"].id), target_reps_min=8, target_reps_max=12)
    first_session = create_session(
        client,
        token,
        routine["id"],
        str(catalog["current"].id),
        datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        reps=[6, 5, 4],
        rpe="9",
        rir=0,
    )
    create_session(
        client,
        token,
        routine["id"],
        str(catalog["current"].id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        reps=[6, 5, 4],
        rpe="9",
        rir=0,
    )

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["type"] == "exercise_swap"
    assert suggestion["apply_payload"]["changes"] == {"exercise_id": str(catalog["best"].id)}
    assert suggestion["input_summary"]["planned_change"]["exercise_name"] == "Chest press"
    assert suggestion["input_summary"]["rule_triggered"] == "poor_tolerance_exercise_swap"

    accept_response = client.post(
        f"/ai/suggestions/{suggestion['id']}/accept", headers={"Authorization": f"Bearer {token}"}
    )
    routine_response = client.get(f"/routines/{routine['id']}", headers={"Authorization": f"Bearer {token}"})
    session_response = client.get(
        f"/workout-sessions/{first_session['id']}", headers={"Authorization": f"Bearer {token}"}
    )

    assert accept_response.status_code == 200
    assert routine_response.json()["exercises"][0]["exercise_id"] == str(catalog["best"].id)
    assert session_response.json()["sets"][0]["exercise_id"] == str(catalog["current"].id)


def test_generate_suggestions_does_not_recommend_exercise_swap_without_alternative(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id), target_reps_min=8, target_reps_max=12)
    create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        reps=[6, 5, 4],
        rpe="9",
        rir=0,
    )
    create_session(
        client,
        token,
        routine["id"],
        str(exercise.id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        reps=[6, 5, 4],
        rpe="9",
        rir=0,
    )

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    assert all(suggestion["type"] != "exercise_swap" for suggestion in response.json())


def test_accept_suggestion_rejects_inaccessible_exercise_swap(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, token, _routine, _session = setup_progression_context(client_with_db)
    other_token = register_and_login(client, "other@example.com", "other_user")
    private_exercise_id = create_private_exercise(client, other_token)
    suggestion = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"}).json()[0]
    _client, session_factory = client_with_db
    db = session_factory()
    try:
        stored = db.get(AiSuggestion, UUID(suggestion["id"]))
        assert stored is not None
        stored.apply_payload = {**stored.apply_payload, "changes": {"exercise_id": private_exercise_id}}
        db.commit()
    finally:
        db.close()

    response = client.post(f"/ai/suggestions/{suggestion['id']}/accept", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422


def test_accept_suggestion_rejects_invalid_apply_payload(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, token, _routine, _session = setup_progression_context(client_with_db)
    suggestion = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"}).json()[0]
    _client, session_factory = client_with_db
    db = session_factory()
    try:
        stored = db.get(AiSuggestion, UUID(suggestion["id"]))
        assert stored is not None
        stored.apply_payload = {**stored.apply_payload, "changes": {"target_sets": 0}}
        db.commit()
    finally:
        db.close()

    response = client.post(f"/ai/suggestions/{suggestion['id']}/accept", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422


def test_generate_suggestions_can_increase_rest(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id), rest_seconds=120)
    create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 1, 10, 0, tzinfo=UTC), reps=[10, 7, 6]
    )
    create_session(
        client, token, routine["id"], str(exercise.id), datetime(2026, 7, 8, 10, 0, tzinfo=UTC), reps=[10, 7, 6]
    )

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["type"] == "increase_rest"
    assert suggestion["apply_payload"]["changes"] == {"rest_seconds": 150}
    assert suggestion["input_summary"]["metrics"]["rep_drop"] == 4


def test_generate_suggestions_can_detect_plateau(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id))
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 1, 10, 0, tzinfo=UTC))
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 8, 10, 0, tzinfo=UTC))
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 15, 10, 0, tzinfo=UTC))

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["type"] == "plateau_detected"
    assert suggestion["apply_payload"]["changes"] == {"target_reps_min": 7, "target_reps_max": 9}


def test_generate_suggestions_can_change_reps(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id), target_reps_min=8, target_reps_max=12)
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 1, 10, 0, tzinfo=UTC), reps=6)
    create_session(client, token, routine["id"], str(exercise.id), datetime(2026, 7, 8, 10, 0, tzinfo=UTC), reps=6)

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["type"] == "change_reps"
    assert suggestion["apply_payload"]["changes"] == {"target_reps_min": 5, "target_reps_max": 7}
    assert suggestion["input_summary"]["rule_triggered"] == "below_rep_target_without_extreme_fatigue"


def test_ollama_provider_enriches_text_without_changing_apply_payload(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def read(self):
            return (
                b'{"response": "{\\"recommendation\\": \\"Recomendacion Ollama\\", '
                b'\\"explanation\\": \\"Explicacion Ollama\\", '
                b'\\"risk_notes\\": \\"Riesgo Ollama\\", '
                b'\\"confidence\\": \\"medium\\"}"}'
            )

    captured_body = {}

    def fake_urlopen(request, timeout):
        captured_body["body"] = request.data.decode("utf-8")
        captured_body["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    monkeypatch.setenv("APP_AI_OLLAMA_MODEL", "llama3.2")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", fake_urlopen)
    client, token, _routine, _session = setup_progression_context(client_with_db)

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    get_settings.cache_clear()
    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["recommendation"] == "Recomendacion Ollama"
    assert suggestion["explanation"] == "Explicacion Ollama"
    assert suggestion["risk_notes"] == "Riesgo Ollama"
    assert suggestion["confidence"] == "medium"
    assert suggestion["apply_payload"]["changes"] == {"target_weight_value": "51.25", "target_weight_unit": "kg"}
    assert suggestion["input_summary"]["ai_provider"]["provider"] == "ollama"
    assert suggestion["input_summary"]["ai_provider"]["fallback_used"] is False
    assert "private" not in captured_body["body"]


def test_ollama_provider_falls_back_on_invalid_response(
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
    client, token, _routine, _session = setup_progression_context(client_with_db)

    response = client.post("/ai/suggestions/generate", headers={"Authorization": f"Bearer {token}"})

    get_settings.cache_clear()
    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["recommendation"] == "Sube el peso objetivo a 51.25 kg."
    assert suggestion["input_summary"]["ai_provider"]["provider"] == "ollama"
    assert suggestion["input_summary"]["ai_provider"]["fallback_used"] is True


def test_analyze_routine_goal_generates_strength_adjustment(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(
        client,
        token,
        str(exercise.id),
        target_sets=2,
        target_reps_min=10,
        target_reps_max=15,
        rest_seconds=60,
        goal="Strength",
    )

    response = client.post(f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["type"] == "routine_goal_adjustment"
    assert suggestion["input_summary"]["rule_triggered"] == "routine_goal_strength_alignment"
    assert suggestion["input_summary"]["analysis_window"] == {"sessions_used": 0}
    assert suggestion["apply_payload"]["changes"] == {
        "target_reps_min": 3,
        "target_reps_max": 6,
        "rest_seconds": 180,
        "target_sets": 3,
    }

    accept_response = client.post(
        f"/ai/suggestions/{suggestion['id']}/accept", headers={"Authorization": f"Bearer {token}"}
    )
    routine_response = client.get(f"/routines/{routine['id']}", headers={"Authorization": f"Bearer {token}"})

    assert accept_response.status_code == 200
    planned = routine_response.json()["exercises"][0]
    assert planned["target_reps_min"] == 3
    assert planned["target_reps_max"] == 6
    assert planned["rest_seconds"] == 180
    assert planned["target_sets"] == 3


def test_analyze_routine_goal_returns_empty_for_unknown_goal(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(client, token, str(exercise.id), goal="Mobility")

    response = client.post(f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    assert response.json() == []


def test_other_user_cannot_analyze_routine_goal(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    routine = create_routine(
        client, owner_token, str(exercise.id), target_reps_min=10, target_reps_max=15, rest_seconds=60
    )

    response = client.post(
        f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {other_token}"}
    )

    assert response.status_code == 404


def test_analyze_routine_goal_deduplicates_pending_matches(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(
        client, token, str(exercise.id), target_sets=2, target_reps_min=10, target_reps_max=15, rest_seconds=60
    )

    first = client.post(f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {token}"})
    second = client.post(f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {token}"})

    assert second.status_code == 201
    assert second.json()[0]["id"] == first.json()[0]["id"]


def test_analyze_routine_goal_expires_obsolete_goal_adjustment(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(
        client, token, str(exercise.id), target_sets=2, target_reps_min=10, target_reps_max=15, rest_seconds=60
    )
    suggestion = client.post(
        f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {token}"}
    ).json()[0]

    update_response = client.put(
        f"/routines/{routine['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Strength plan",
            "goal": "Strength",
            "exercises": [
                {
                    "exercise_id": str(exercise.id),
                    "position": 1,
                    "target_sets": 3,
                    "target_reps_min": 3,
                    "target_reps_max": 6,
                    "rest_seconds": 180,
                }
            ],
        },
    )
    response = client.post(f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {token}"})
    list_response = client.get("/ai/suggestions", headers={"Authorization": f"Bearer {token}"})

    assert update_response.status_code == 200
    assert response.json() == []
    stored = next(item for item in list_response.json() if item["id"] == suggestion["id"])
    assert stored["status"] == "expired"


def test_ollama_enriches_routine_goal_adjustment_without_changing_payload(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        def read(self):
            return (
                b'{"response": "{\\"recommendation\\": \\"Ajuste Ollama\\", '
                b'\\"explanation\\": \\"Explicacion Ollama\\", '
                b'\\"risk_notes\\": null, '
                b'\\"confidence\\": \\"medium\\"}"}'
            )

    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", lambda _request, timeout: FakeResponse())
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine = create_routine(
        client, token, str(exercise.id), target_sets=2, target_reps_min=10, target_reps_max=15, rest_seconds=60
    )

    response = client.post(f"/ai/routines/{routine['id']}/analyze-goal", headers={"Authorization": f"Bearer {token}"})

    get_settings.cache_clear()
    assert response.status_code == 201
    suggestion = response.json()[0]
    assert suggestion["recommendation"] == "Ajuste Ollama"
    assert suggestion["explanation"] == "Explicacion Ollama"
    assert suggestion["apply_payload"]["changes"] == {
        "target_reps_min": 3,
        "target_reps_max": 6,
        "rest_seconds": 180,
        "target_sets": 3,
    }
