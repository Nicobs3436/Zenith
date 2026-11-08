from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.exercise import Exercise
from app.infrastructure.db.models.rank import UserRankProgress
from app.infrastructure.db.seed import seed_database
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
    db = testing_session_local()
    try:
        seed_database(db)
    finally:
        db.close()

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


def create_session(
    client: TestClient,
    token: str,
    exercise_id: str,
    started_at: datetime,
    sets: list[dict[str, Any]],
) -> dict[str, Any]:
    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": started_at.isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [{"exercise_id": exercise_id, **workout_set} for workout_set in sets],
        },
    )
    assert response.status_code == 201
    return response.json()


def count_rank_snapshots(session_factory: SessionFactory) -> int:
    db = session_factory()
    try:
        return db.query(UserRankProgress).count()
    finally:
        db.close()


def test_list_ranks_returns_seeded_ranks(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db

    response = client.get("/ranks")

    assert response.status_code == 200
    assert [rank["name"] for rank in response.json()] == [
        "Novato",
        "Principiante",
        "Intermedio",
        "Avanzado",
        "Atleta",
        "Elite",
        "Leyenda",
    ]


def test_user_without_weighted_sets_stays_in_initial_rank(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, _session_factory = client_with_db
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["rank"]["name"] == "Novato"
    assert data["next_rank"]["name"] == "Principiante"
    assert data["points_to_next_rank"] == "100.00"
    assert data["score"] == "0.00"


def test_weighted_volume_increases_rank_score(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "100", "weight_unit": "kg"}],
    )

    response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["volume_score"] == "10.00"
    assert data["score"] == "10.00"


def test_progression_increases_score_without_session_points(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 5, "weight_value": "100", "weight_unit": "kg"}],
    )
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 5, "weight_value": "120", "weight_unit": "kg"}],
    )

    response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["progression_score"] == "100.00"
    assert data["breadth_score"] == "25.00"


def test_unweighted_sessions_do_not_increase_rank_score(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory, name="Push-up")
    token = register_and_login(client, "owner@example.com", "owner_user")
    for index in range(10):
        create_session(
            client,
            token,
            str(exercise.id),
            datetime(2026, 7, 1, 10, 0, tzinfo=UTC) + timedelta(days=index),
            [{"set_number": 1, "reps": 20}],
        )

    response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == "0.00"
    assert data["rank"]["name"] == "Novato"


def test_sessions_without_weight_progression_do_not_get_progression_or_breadth_points(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    for index in range(3):
        create_session(
            client,
            token,
            str(exercise.id),
            datetime(2026, 7, 1, 10, 0, tzinfo=UTC) + timedelta(days=index),
            [{"set_number": 1, "reps": 5, "weight_value": "100", "weight_unit": "kg"}],
        )

    response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["progression_score"] == "0.00"
    assert data["breadth_score"] == "0.00"
    assert data["volume_score"] == "15.00"


def test_rank_score_does_not_include_other_users_data(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    create_session(
        client,
        owner_token,
        str(exercise.id),
        datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "200", "weight_unit": "kg"}],
    )

    response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 200
    assert response.json()["score"] == "0.00"


def test_rank_recalculate_persists_snapshot(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "100", "weight_unit": "kg"}],
    )

    response = client.post("/users/me/rank/recalculate", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["calculated_at"] is not None


def test_create_workout_session_recalculates_rank_snapshot(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "100", "weight_unit": "kg"}],
    )

    assert count_rank_snapshots(session_factory) == 1


def test_update_workout_session_recalculates_rank_snapshot(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "100", "weight_unit": "kg"}],
    )

    response = client.put(
        f"/workout-sessions/{session['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "started_at": datetime(2026, 7, 2, 10, 0, tzinfo=UTC).isoformat(),
            "timezone": "Europe/Madrid",
            "sets": [
                {
                    "exercise_id": str(exercise.id),
                    "set_number": 1,
                    "reps": 10,
                    "weight_value": "120",
                    "weight_unit": "kg",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert count_rank_snapshots(session_factory) == 2


def test_delete_workout_session_recalculates_rank_and_excludes_deleted_session(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "100", "weight_unit": "kg"}],
    )

    delete_response = client.delete(
        f"/workout-sessions/{session['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    rank_response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"})

    assert delete_response.status_code == 204
    assert count_rank_snapshots(session_factory) == 2
    assert rank_response.status_code == 200
    assert rank_response.json()["score"] == "0.00"


def test_rank_response_returns_no_next_rank_at_max_rank(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": n, "reps": 100, "weight_value": "2500", "weight_unit": "kg"} for n in range(1, 5)],
    )

    response = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["rank"]["name"] == "Leyenda"
    assert data["next_rank"] is None
    assert data["points_to_next_rank"] is None


def test_rank_volume_normalizes_lb_to_kg(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "100", "weight_unit": "lb"}],
    )

    data = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"}).json()

    # 100 lb x 10 = 1000 lb = 453.59 kg -> 4.54 puntos.
    assert data["volume_score"] == "4.54"


def test_rank_progression_uses_best_set_of_first_session_as_baseline(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [
            {"set_number": 1, "reps": 5, "weight_value": "40", "weight_unit": "kg"},
            {"set_number": 2, "reps": 5, "weight_value": "100", "weight_unit": "kg"},
        ],
    )
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 9, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 5, "weight_value": "100", "weight_unit": "kg"}],
    )

    data = client.get("/users/me/rank", headers={"Authorization": f"Bearer {token}"}).json()

    # El calentamiento de 40 kg no cuenta como referencia: no hay progreso real.
    assert data["progression_score"] == "0.00"
    assert data["breadth_score"] == "0.00"
