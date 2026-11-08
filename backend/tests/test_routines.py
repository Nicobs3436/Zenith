from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import TypeAlias

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.exercise import Exercise
from app.infrastructure.db.session import get_db
from app.main import app

SessionFactory: TypeAlias = Callable[[], Session]


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


def create_private_exercise(client: TestClient, token: str, name: str = "Private squat") -> str:
    response = client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "difficulty": "beginner"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def routine_payload(exercise_id: str) -> dict:
    return {
        "name": "Lower body",
        "goal": "Strength",
        "exercises": [
            {
                "exercise_id": exercise_id,
                "position": 1,
                "target_sets": 3,
                "target_reps_min": 5,
                "target_reps_max": 8,
                "target_rpe": "8",
                "target_rir": 2,
                "rest_seconds": 180,
            }
        ],
    }


def test_create_routine_with_global_exercise(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json=routine_payload(str(exercise.id)),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Lower body"
    assert data["exercises"][0]["exercise_id"] == str(exercise.id)
    assert data["exercises"][0]["position"] == 1


def test_create_routine_with_own_exercise(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _ = client_with_db
    token = register_and_login(client, "owner@example.com", "owner_user")
    exercise_id = create_private_exercise(client, token)

    response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json=routine_payload(exercise_id),
    )

    assert response.status_code == 201
    assert response.json()["exercises"][0]["exercise_id"] == exercise_id


def test_create_routine_rejects_empty_exercise_list(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _ = client_with_db
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Empty routine", "exercises": []},
    )

    assert response.status_code == 422


def test_create_routine_rejects_another_users_private_exercise(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, _ = client_with_db
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    exercise_id = create_private_exercise(client, owner_token)

    response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {other_token}"},
        json=routine_payload(exercise_id),
    )

    assert response.status_code == 422


def test_list_routines_returns_only_current_users_routines(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    client.post("/routines", headers={"Authorization": f"Bearer {owner_token}"}, json=routine_payload(str(exercise.id)))

    response = client.get("/routines", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_create_workout_session_with_sets(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json=routine_payload(str(exercise.id)),
    )
    routine_id = routine_response.json()["id"]
    started_at = datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat()
    finished_at = datetime(2026, 7, 2, 11, 0, tzinfo=UTC).isoformat()

    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "routine_id": routine_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "timezone": "Europe/Madrid",
            "sets": [
                {
                    "exercise_id": str(exercise.id),
                    "set_number": 1,
                    "reps": 5,
                    "weight_value": "100",
                    "weight_unit": "kg",
                    "rpe": "8",
                    "rir": 2,
                    "rest_seconds": 180,
                }
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["routine_id"] == routine_id
    assert data["sets"][0]["exercise_id"] == str(exercise.id)
    assert data["sets"][0]["reps"] == 5


def test_create_workout_session_rejects_invalid_set_values(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": -1}],
        },
    )

    assert response.status_code == 422


def test_list_workout_sessions_returns_only_current_users_sessions(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
        },
    )

    response = client.get("/workout-sessions", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_update_routine_replaces_exercises(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    first_exercise = seed_global_exercise(session_factory, "Squat")
    second_exercise = seed_global_exercise(session_factory, "Deadlift")
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json=routine_payload(str(first_exercise.id)),
    )
    routine_id = create_response.json()["id"]

    response = client.put(
        f"/routines/{routine_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Pull day",
            "description": "Updated plan",
            "goal": "Hypertrophy",
            "exercises": [
                {
                    "exercise_id": str(second_exercise.id),
                    "position": 1,
                    "target_sets": 4,
                    "target_reps_min": 8,
                    "target_reps_max": 12,
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Pull day"
    assert data["description"] == "Updated plan"
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["exercise_id"] == str(second_exercise.id)
    assert data["exercises"][0]["target_sets"] == 4


def test_update_routine_returns_404_for_another_users_routine(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    create_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=routine_payload(str(exercise.id)),
    )
    routine_id = create_response.json()["id"]

    response = client.put(
        f"/routines/{routine_id}",
        headers={"Authorization": f"Bearer {other_token}"},
        json=routine_payload(str(exercise.id)),
    )

    assert response.status_code == 404


def test_update_routine_rejects_another_users_private_exercise(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    private_exercise_id = create_private_exercise(client, owner_token)
    create_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {other_token}"},
        json=routine_payload(str(exercise.id)),
    )
    routine_id = create_response.json()["id"]

    response = client.put(
        f"/routines/{routine_id}",
        headers={"Authorization": f"Bearer {other_token}"},
        json=routine_payload(private_exercise_id),
    )

    assert response.status_code == 422


def test_update_workout_session_replaces_sets(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    first_exercise = seed_global_exercise(session_factory, "Squat")
    second_exercise = seed_global_exercise(session_factory, "Bench press")
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(first_exercise.id), "set_number": 1, "reps": 5}],
        },
    )
    session_id = create_response.json()["id"]

    response = client.put(
        f"/workout-sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 2, 12, 0, tzinfo=UTC).isoformat(),
            "finished_at": datetime(2026, 7, 2, 13, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "notes": "Updated session",
            "sets": [
                {"exercise_id": str(second_exercise.id), "set_number": 1, "reps": 8, "weight_value": "60", "weight_unit": "kg"},
                {"exercise_id": str(second_exercise.id), "set_number": 2, "reps": 7, "weight_value": "60", "weight_unit": "kg"},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Updated session"
    assert len(data["sets"]) == 2
    assert {workout_set["exercise_id"] for workout_set in data["sets"]} == {str(second_exercise.id)}
    assert [workout_set["reps"] for workout_set in data["sets"]] == [8, 7]


def test_update_workout_session_rejects_another_users_routine(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    routine_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=routine_payload(str(exercise.id)),
    )
    session_response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {other_token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
        },
    )

    response = client.put(
        f"/workout-sessions/{session_response.json()['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
        json={
            "routine_id": routine_response.json()["id"],
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
        },
    )

    assert response.status_code == 422


def test_delete_routine_hides_it_without_deleting_associated_sessions(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json=routine_payload(str(exercise.id)),
    )
    routine_id = routine_response.json()["id"]
    session_response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "routine_id": routine_id,
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
        },
    )

    response = client.delete(f"/routines/{routine_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert client.get("/routines", headers={"Authorization": f"Bearer {token}"}).json() == []
    assert client.get(f"/routines/{routine_id}", headers={"Authorization": f"Bearer {token}"}).status_code == 404
    sessions_response = client.get("/workout-sessions", headers={"Authorization": f"Bearer {token}"})
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["id"] == session_response.json()["id"]
    assert sessions_response.json()[0]["routine_id"] == routine_id


def test_delete_routine_returns_404_for_another_users_routine(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    routine_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=routine_payload(str(exercise.id)),
    )

    response = client.delete(
        f"/routines/{routine_response.json()['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_create_workout_session_rejects_deleted_routine(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    routine_response = client.post(
        "/routines",
        headers={"Authorization": f"Bearer {token}"},
        json=routine_payload(str(exercise.id)),
    )
    routine_id = routine_response.json()["id"]
    client.delete(f"/routines/{routine_id}", headers={"Authorization": f"Bearer {token}"})

    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "routine_id": routine_id,
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
        },
    )

    assert response.status_code == 422


def test_delete_workout_session_hides_it(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session_response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
        },
    )
    session_id = session_response.json()["id"]

    response = client.delete(f"/workout-sessions/{session_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert client.get("/workout-sessions", headers={"Authorization": f"Bearer {token}"}).json() == []
    assert client.get(f"/workout-sessions/{session_id}", headers={"Authorization": f"Bearer {token}"}).status_code == 404


def test_delete_workout_session_returns_404_for_another_users_session(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    session_response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
        },
    )

    response = client.delete(
        f"/workout-sessions/{session_response.json()['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_update_workout_session_keeps_link_to_deleted_routine(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    headers = {"Authorization": f"Bearer {token}"}
    routine_id = client.post("/routines", headers=headers, json=routine_payload(str(exercise.id))).json()["id"]
    session_payload = {
        "routine_id": routine_id,
        "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
        "timezone": "Europe/Madrid",
        "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
    }
    session_id = client.post("/workout-sessions", headers=headers, json=session_payload).json()["id"]
    client.delete(f"/routines/{routine_id}", headers=headers)

    response = client.put(
        f"/workout-sessions/{session_id}",
        headers=headers,
        json={**session_payload, "notes": "Editada tras borrar la rutina"},
    )

    assert response.status_code == 200
    assert response.json()["routine_id"] == routine_id
    assert response.json()["notes"] == "Editada tras borrar la rutina"


def test_update_workout_session_rejects_switching_to_deleted_routine(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    headers = {"Authorization": f"Bearer {token}"}
    deleted_routine_id = client.post("/routines", headers=headers, json=routine_payload(str(exercise.id))).json()["id"]
    client.delete(f"/routines/{deleted_routine_id}", headers=headers)
    session_payload = {
        "routine_id": None,
        "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
        "timezone": "Europe/Madrid",
        "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}],
    }
    session_id = client.post("/workout-sessions", headers=headers, json=session_payload).json()["id"]

    response = client.put(
        f"/workout-sessions/{session_id}",
        headers=headers,
        json={**session_payload, "routine_id": deleted_routine_id},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "set_override",
    [
        {"weight_value": "1000000", "weight_unit": "kg"},
        {"weight_value": "100.123", "weight_unit": "kg"},
        {"reps": 100000},
        {"rest_seconds": 99999},
        {"rpe": "8.25"},
    ],
)
def test_create_workout_session_rejects_unrealistic_values(
    client_with_db: tuple[TestClient, SessionFactory], set_override: dict
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5, **set_override}],
        },
    )

    assert response.status_code == 422


def test_create_workout_session_rejects_too_many_sets(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": str(exercise.id), "set_number": 1, "reps": 5}] * 301,
        },
    )

    assert response.status_code == 422


def test_create_routine_rejects_unrealistic_target_weight(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    payload = routine_payload(str(exercise.id))
    payload["exercises"][0].update({"target_weight_value": "999999", "target_weight_unit": "kg"})

    response = client.post("/routines", headers={"Authorization": f"Bearer {token}"}, json=payload)

    assert response.status_code == 422
