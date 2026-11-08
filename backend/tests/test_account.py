from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
from app.infrastructure.db.models import CoachProfile, Exercise, RefreshToken, Routine, User, WorkoutSession, WorkoutSet
from app.infrastructure.db.session import get_db
from app.main import app
from tests.test_routines import SessionFactory, register_and_login, routine_payload, seed_global_exercise


@pytest.fixture()
def client_with_db() -> Generator[tuple[TestClient, SessionFactory], None, None]:
    # SQLite no aplica claves foraneas por defecto: se activan para que un orden de borrado
    # incorrecto falle aqui igual que fallaria en PostgreSQL.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

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


PASSWORD = "password123"


def populate(client: TestClient, token: str, global_exercise_id: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    private_id = client.post(
        "/exercises", headers=headers, json={"name": "Mi ejercicio", "muscle_group_ids": [], "equipment_ids": []}
    ).json()["id"]
    routine_id = client.post("/routines", headers=headers, json=routine_payload(global_exercise_id)).json()["id"]
    response = client.post(
        "/workout-sessions",
        headers=headers,
        json={
            "routine_id": routine_id,
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [
                {
                    "exercise_id": global_exercise_id,
                    "set_number": 1,
                    "reps": 5,
                    "weight_value": "100",
                    "weight_unit": "kg",
                },
                {"exercise_id": private_id, "set_number": 2, "reps": 8},
            ],
        },
    )
    assert response.status_code == 201
    coach = client.post(
        "/ai/coach/messages",
        headers=headers,
        json={"message": "Quiero ganar fuerza", "personal_data_acknowledged": True},
    )
    assert coach.status_code == 200


def test_export_contains_user_data_without_secrets(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    populate(client, token, str(exercise.id))

    response = client.get("/users/me/export", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["user"]["email"] == "owner@example.com"
    assert "password_hash" not in data["user"]
    assert len(data["routines"]) == 1
    assert len(data["workout_sets"]) == 2
    assert len(data["private_exercises"]) == 1
    assert len(data["coach_profiles"]) == 1
    assert "password_hash" not in response.text and "token_hash" not in response.text


def test_delete_account_requires_password_and_removes_only_own_data(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    populate(client, token, str(exercise.id))
    populate(client, other_token, str(exercise.id))
    headers = {"Authorization": f"Bearer {token}"}

    wrong = client.request("DELETE", "/users/me", headers=headers, json={"password": "nope"})
    deleted = client.request("DELETE", "/users/me", headers=headers, json={"password": PASSWORD})

    assert wrong.status_code == 403
    assert deleted.status_code == 204
    assert client.get("/users/me", headers=headers).status_code == 401
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(Routine)) == 1
        assert db.scalar(select(func.count()).select_from(WorkoutSession)) == 1
        assert db.scalar(select(func.count()).select_from(WorkoutSet)) == 2
        assert db.scalar(select(func.count()).select_from(CoachProfile)) == 1
        assert db.scalar(select(func.count()).select_from(RefreshToken)) == 1
        # Queda el ejercicio global y el privado del otro usuario.
        assert db.scalar(select(func.count()).select_from(Exercise)) == 2
    assert client.get("/routines", headers={"Authorization": f"Bearer {other_token}"}).json()
