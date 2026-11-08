from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.base import Base
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
    client.post("/auth/register", json={"email": email, "username": username, "password": password})
    response = client.post("/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def seed_catalog(session_factory: SessionFactory) -> tuple[MuscleGroup, Equipment]:
    db = session_factory()
    try:
        muscle = MuscleGroup(name="Chest")
        equipment = Equipment(name="Barbell")
        db.add_all([muscle, equipment])
        db.commit()
        db.refresh(muscle)
        db.refresh(equipment)
        return muscle, equipment
    finally:
        db.close()


def seed_global_exercise(session_factory: SessionFactory) -> Exercise:
    db = session_factory()
    try:
        muscle = MuscleGroup(name="Back")
        equipment = Equipment(name="Pull-up bar")
        exercise = Exercise(
            name="Pull-up",
            description="Vertical pull bodyweight exercise.",
            difficulty="intermediate",
            is_global=True,
            muscle_groups=[muscle],
            equipment=[equipment],
        )
        db.add(exercise)
        db.commit()
        db.refresh(exercise)
        return exercise
    finally:
        db.close()


def test_list_exercises_without_token_returns_only_global_exercises(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_global_exercise(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    muscle, equipment = seed_catalog(session_factory)
    client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Private bench press",
            "difficulty": "beginner",
            "muscle_group_ids": [str(muscle.id)],
            "equipment_ids": [str(equipment.id)],
        },
    )

    response = client.get("/exercises")

    assert response.status_code == 200
    assert [exercise["name"] for exercise in response.json()] == ["Pull-up"]


def test_list_exercises_with_token_returns_global_and_own_exercises(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_global_exercise(session_factory)
    muscle, equipment = seed_catalog(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Private bench press",
            "difficulty": "beginner",
            "muscle_group_ids": [str(muscle.id)],
            "equipment_ids": [str(equipment.id)],
        },
    )

    response = client.get("/exercises", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [exercise["name"] for exercise in response.json()] == ["Private bench press", "Pull-up"]


def test_create_exercise_requires_auth(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    muscle, equipment = seed_catalog(session_factory)

    response = client.post(
        "/exercises",
        json={
            "name": "Bench press",
            "muscle_group_ids": [str(muscle.id)],
            "equipment_ids": [str(equipment.id)],
        },
    )

    assert response.status_code == 401


def test_create_exercise_creates_own_non_global_exercise(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    muscle, equipment = seed_catalog(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")

    response = client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Bench press",
            "difficulty": "beginner",
            "is_global": True,
            "muscle_group_ids": [str(muscle.id)],
            "equipment_ids": [str(equipment.id)],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Bench press"
    assert data["is_global"] is False
    assert data["created_by_user_id"] is not None
    assert data["muscle_groups"] == [{"id": str(muscle.id), "name": "Chest"}]
    assert data["equipment"] == [{"id": str(equipment.id), "name": "Barbell"}]


def test_get_global_exercise_detail_without_token(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    exercise = seed_global_exercise(session_factory)

    response = client.get(f"/exercises/{exercise.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Pull-up"


def test_get_own_exercise_detail_with_token(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    muscle, equipment = seed_catalog(session_factory)
    token = register_and_login(client, "owner@example.com", "owner_user")
    create_response = client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Bench press",
            "muscle_group_ids": [str(muscle.id)],
            "equipment_ids": [str(equipment.id)],
        },
    )
    exercise_id = create_response.json()["id"]

    response = client.get(f"/exercises/{exercise_id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["name"] == "Bench press"


def test_cannot_get_another_users_private_exercise(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    muscle, equipment = seed_catalog(session_factory)
    owner_token = register_and_login(client, "owner@example.com", "owner_user")
    other_token = register_and_login(client, "other@example.com", "other_user")
    create_response = client.post(
        "/exercises",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Private lift",
            "muscle_group_ids": [str(muscle.id)],
            "equipment_ids": [str(equipment.id)],
        },
    )
    exercise_id = create_response.json()["id"]

    response = client.get(f"/exercises/{exercise_id}", headers={"Authorization": f"Bearer {other_token}"})

    assert response.status_code == 404


def test_list_muscle_groups_and_equipment(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    muscle, equipment = seed_catalog(session_factory)

    muscle_response = client.get("/muscle-groups")
    equipment_response = client.get("/equipment")

    assert muscle_response.status_code == 200
    assert equipment_response.status_code == 200
    assert muscle_response.json() == [{"id": str(muscle.id), "name": "Chest"}]
    assert equipment_response.json() == [{"id": str(equipment.id), "name": "Barbell"}]
