import pytest
from fastapi.testclient import TestClient

from tests.test_ai_training_plans import SessionFactory, client_with_db, register_and_login, seed_exercises


def test_coach_v2_requires_scientific_profile_before_plan(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "coach-v2-required@example.com", "coach_v2_required")

    state = client.get("/ai/coach/v2", headers={"Authorization": f"Bearer {token}"})
    plan = client.post("/ai/coach/v2/generate-plan", headers={"Authorization": f"Bearer {token}"})

    assert state.status_code == 200
    data = state.json()
    assert data["ready_for_plan"] is False
    assert data["missing_required_fields"][0] == "personal_data_acknowledged"
    assert "sexo biologico" in data["assistant_message"].lower() or "datos personales" in data["assistant_message"].lower()
    assert plan.status_code == 422


def test_coach_v2_understands_short_answers_from_context(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "coach-v2-context@example.com", "coach_v2_context")
    headers = {"Authorization": f"Bearer {token}"}

    messages = [
        "acepto",
        "hipertrofia",
        "masculino",
        "34",
        "178",
        "82",
        "intermedio",
        "4",
        "120",
        "gimnasio comercial, prioriza pecho y espalda, sin peso muerto",
    ]
    response = None
    for message in messages:
        response = client.post(
            "/ai/coach/v2/messages",
            headers=headers,
            json={"message": message, "personal_data_acknowledged": True, "sensitive_data_acknowledged": False},
        )

    assert response is not None
    assert response.status_code == 200
    data = response.json()
    profile = data["profile"]
    assert data["ready_for_plan"] is True
    assert profile["goal"] == "hypertrophy"
    assert profile["biological_sex"] == "male"
    assert profile["age"] == 34
    assert profile["height_cm"] == 178
    assert profile["weight_kg"] == 82
    assert profile["days_per_week"] == 4
    assert profile["session_duration_minutes"] == 120
    assert "mancuernas" in profile["equipment"]
    assert "pecho" in profile["priorities"]
    assert "espalda" in profile["priorities"]
    assert "peso muerto" in profile["avoided_exercises"]


@pytest.mark.parametrize(
    ("goal_text", "goal"),
    [
        ("fuerza", "strength"),
        ("hipertrofia", "hypertrophy"),
        ("perdida de grasa", "fat_loss"),
        ("salud general", "general_health"),
        ("resistencia", "endurance"),
    ],
)
def test_coach_v2_generates_plan_for_all_supported_goals(
    client_with_db: tuple[TestClient, SessionFactory], goal_text: str, goal: str
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory, count=8)
    token = register_and_login(client, f"coach-v2-{goal}@example.com", f"coach_v2_{goal}")

    response = client.post(
        "/ai/coach/v2/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": f"acepto, objetivo {goal_text}, femenino, 31 anos, 165 cm, 62 kg, intermedio, 3 dias, 60 minutos, gimnasio comercial",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": False,
        },
    )
    plan_response = client.post("/ai/coach/v2/generate-plan", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["ready_for_plan"] is True
    assert response.json()["profile"]["goal"] == goal
    assert response.json()["profile"]["biological_sex"] == "female"
    assert plan_response.status_code == 201
    plan = plan_response.json()
    assert plan["goal"] == goal
    assert plan["status"] == "draft"
    assert len(plan["plan_payload"]["routines"]) == 3


def test_coach_v2_creates_fatigue_proposal_from_conversation(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "coach-v2-fatigue@example.com", "coach_v2_fatigue")

    response = client.post(
        "/ai/coach/v2/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "me noto reventado y no progreso", "personal_data_acknowledged": False, "sensitive_data_acknowledged": False},
    )

    assert response.status_code == 200
    proposals = response.json()["proposals"]
    assert any(proposal["type"] == "fatigue_review" and proposal["status"] == "pending" for proposal in proposals)
