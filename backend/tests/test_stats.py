from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.exercise import Exercise, MuscleGroup
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
    client.post("/auth/register", json={"email": email, "username": username, "password": password})
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def seed_global_exercise(
    session_factory: SessionFactory,
    name: str = "Bench press",
    muscle_names: list[str] | None = None,
) -> Exercise:
    db = session_factory()
    try:
        muscle_groups = []
        for muscle_name in muscle_names or []:
            muscle_group = MuscleGroup(name=muscle_name)
            db.add(muscle_group)
            muscle_groups.append(muscle_group)
        exercise = Exercise(name=name, difficulty="beginner", is_global=True)
        exercise.muscle_groups = muscle_groups
        db.add(exercise)
        db.commit()
        db.refresh(exercise)
        return exercise
    finally:
        db.close()


def create_private_exercise(client: TestClient, token: str, name: str = "Private lift") -> str:
    response = client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "difficulty": "beginner"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_session(
    client: TestClient,
    token: str,
    exercise_id: str,
    started_at: datetime,
    sets: list[dict[str, Any]],
    finished_at: datetime | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "started_at": started_at.isoformat(),
        "timezone": "Europe/Madrid",
        "sets": [{"exercise_id": exercise_id, **workout_set} for workout_set in sets],
    }
    if finished_at is not None:
        payload["finished_at"] = finished_at.isoformat()

    response = client.post(
        "/workout-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def test_exercise_stats_calculate_sets_reps_volume_and_load(
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
            {"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"},
            {"set_number": 2, "reps": 5, "weight_value": "60", "weight_unit": "kg"},
        ],
    )

    response = client.get("/stats/exercises", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()[0]
    assert data["exercise_id"] == str(exercise.id)
    assert data["weight_unit"] == "kg"
    assert data["total_sets"] == 2
    assert data["total_reps"] == 15
    assert data["total_volume"] == "800.00"
    assert data["max_weight"] == "60.00"
    assert data["avg_weight"] == "55.00"
    assert data["best_estimated_1rm"] == "70.00"


def test_exercise_stats_do_not_include_other_users_sessions(
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
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"}],
    )

    response = client.get("/stats/exercises", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_exercise_stats_exclude_deleted_sessions(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    session = create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"}],
    )

    delete_response = client.delete(
        f"/workout-sessions/{session['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    response = client.get("/stats/exercises", headers={"Authorization": f"Bearer {token}"})

    assert delete_response.status_code == 204
    assert response.status_code == 200
    assert response.json() == []


def test_exercise_stats_filter_by_date_range(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"}],
    )
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 10, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 5, "weight_value": "60", "weight_unit": "kg"}],
    )

    response = client.get(
        "/stats/exercises",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "start_date": datetime(2026, 7, 2, 0, 0, tzinfo=UTC).isoformat(),
            "end_date": datetime(2026, 7, 31, 23, 59, tzinfo=UTC).isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["total_reps"] == 5
    assert response.json()[0]["total_volume"] == "300.00"


@pytest.mark.parametrize(
    ("period", "expected_prefix"),
    [
        ("day", "2026-07-08T00:00:00"),
        ("week", "2026-07-06T00:00:00"),
        ("month", "2026-07-01T00:00:00"),
    ],
)
def test_exercise_stats_group_by_period(
    client_with_db: tuple[TestClient, SessionFactory],
    period: str,
    expected_prefix: str,
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"}],
    )

    response = client.get(
        f"/stats/exercises/{exercise.id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"period": period},
    )

    assert response.status_code == 200
    assert response.json()["points"][0]["period_start"].startswith(expected_prefix)


def test_exercise_stats_keep_kg_and_lb_separate(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [
            {"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"},
            {"set_number": 2, "reps": 10, "weight_value": "100", "weight_unit": "lb"},
        ],
    )

    response = client.get("/stats/exercises", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [item["weight_unit"] for item in response.json()] == ["kg", "lb"]


def test_exercise_stats_count_unweighted_sets_without_load_metrics(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory, name="Push-up")
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 20}],
    )

    response = client.get("/stats/exercises", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()[0]
    assert data["weight_unit"] is None
    assert data["total_sets"] == 1
    assert data["total_reps"] == 20
    assert data["total_volume"] is None
    assert data["max_weight"] is None
    assert data["best_estimated_1rm"] is None


def test_exercise_stats_return_404_for_inaccessible_private_exercise(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, _session_factory = client_with_db
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    exercise_id = create_private_exercise(client, owner_token)

    response = client.get(
        f"/stats/exercises/{exercise_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_stats_overview_returns_kpis_volume_muscles_and_top_exercises(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    bench = seed_global_exercise(session_factory, name="Bench press", muscle_names=["Pecho"])
    row = seed_global_exercise(session_factory, name="Barbell row", muscle_names=["Espalda"])
    token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    create_session(
        client,
        token,
        str(bench.id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        [
            {"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"},
            {"set_number": 2, "reps": 5, "weight_value": "60", "weight_unit": "kg"},
        ],
        finished_at=datetime(2026, 7, 8, 11, 0, tzinfo=UTC),
    )
    create_session(
        client,
        token,
        str(row.id),
        datetime(2026, 7, 15, 14, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 8, "weight_value": "80", "weight_unit": "kg"}],
        finished_at=datetime(2026, 7, 15, 14, 30, tzinfo=UTC),
    )
    create_session(
        client,
        token,
        str(bench.id),
        datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "100", "weight_unit": "lb"}],
    )
    create_session(
        client,
        other_token,
        str(bench.id),
        datetime(2026, 7, 17, 10, 0, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "200", "weight_unit": "kg"}],
    )

    response = client.get(
        "/stats/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "period": "week",
            "start_date": datetime(2026, 7, 1, 0, 0, tzinfo=UTC).isoformat(),
            "end_date": datetime(2026, 7, 31, 23, 59, tzinfo=UTC).isoformat(),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["kpis"] == {
        "total_sets": 4,
        "session_count": 3,
        "training_hours": "1.50",
        "pr_count": 0,
    }
    assert data["volume_by_unit"] == [
        {"weight_unit": "kg", "total_volume": "1440.00"},
        {"weight_unit": "lb", "total_volume": "1000.00"},
    ]
    assert data["muscle_groups"] == [
        {"name": "Pecho", "total_sets": 3},
        {"name": "Espalda", "total_sets": 1},
    ]
    assert data["volume_points"] == [
        {
            "period_start": "2026-07-06T00:00:00Z",
            "weight_unit": "kg",
            "total_volume": "800.00",
            "total_sets": 2,
            "session_count": 1,
        },
        {
            "period_start": "2026-07-13T00:00:00Z",
            "weight_unit": "kg",
            "total_volume": "640.00",
            "total_sets": 1,
            "session_count": 1,
        },
        {
            "period_start": "2026-07-13T00:00:00Z",
            "weight_unit": "lb",
            "total_volume": "1000.00",
            "total_sets": 1,
            "session_count": 1,
        },
    ]
    assert data["top_exercises"][0]["exercise_name"] == "Barbell row"
    assert data["top_exercises"][0]["best_estimated_1rm"] == "101.33"


def test_stats_overview_filters_weight_unit_without_mixing_units(
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
            {"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"},
            {"set_number": 2, "reps": 10, "weight_value": "100", "weight_unit": "lb"},
        ],
    )

    response = client.get(
        "/stats/overview",
        headers={"Authorization": f"Bearer {token}"},
        params={"weight_unit": "kg"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["kpis"]["total_sets"] == 1
    assert data["volume_by_unit"] == [{"weight_unit": "kg", "total_volume": "500.00"}]
    assert {point["weight_unit"] for point in data["volume_points"]} == {"kg"}


def test_stats_overview_counts_only_real_personal_records(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    bench = seed_global_exercise(session_factory, name="Bench press", muscle_names=["Pecho"])
    token = register_and_login(client, "owner@example.com", "owner_user")
    for day, weight in [(1, "100"), (8, "110"), (15, "105"), (22, "115")]:
        create_session(
            client,
            token,
            str(bench.id),
            datetime(2026, 7, day, 10, 0, tzinfo=UTC),
            [{"set_number": 1, "reps": 5, "weight_value": weight, "weight_unit": "kg"}],
        )
    headers = {"Authorization": f"Bearer {token}"}

    all_time = client.get("/stats/overview", headers=headers).json()
    last_week = client.get(
        "/stats/overview",
        headers=headers,
        params={"start_date": datetime(2026, 7, 14, 0, 0, tzinfo=UTC).isoformat()},
    ).json()

    assert all_time["kpis"]["pr_count"] == 2
    assert last_week["kpis"]["pr_count"] == 1


def test_stats_group_days_by_session_local_timezone(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    # 23:30 UTC del 8 de julio = 01:30 del 9 de julio en Madrid.
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 8, 23, 30, tzinfo=UTC),
        [{"set_number": 1, "reps": 10, "weight_value": "50", "weight_unit": "kg"}],
    )

    response = client.get(
        f"/stats/exercises/{exercise.id}",
        headers={"Authorization": f"Bearer {token}"},
        params={"period": "day"},
    )

    assert response.json()["points"][0]["period_start"].startswith("2026-07-09")


def test_stats_ignore_zero_rep_sets_for_max_and_high_rep_sets_for_1rm(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_session(
        client,
        token,
        str(exercise.id),
        datetime(2026, 7, 8, 10, 0, tzinfo=UTC),
        [
            {"set_number": 1, "reps": 0, "weight_value": "200", "weight_unit": "kg"},
            {"set_number": 2, "reps": 20, "weight_value": "100", "weight_unit": "kg"},
            {"set_number": 3, "reps": 3, "weight_value": "90", "weight_unit": "kg"},
        ],
    )

    data = client.get("/stats/exercises", headers={"Authorization": f"Bearer {token}"}).json()[0]

    assert data["max_weight"] == "100.00"
    # Solo la serie de 3 reps entra en Epley: 90 * (1 + 3/30) = 99.
    assert data["best_estimated_1rm"] == "99.00"
