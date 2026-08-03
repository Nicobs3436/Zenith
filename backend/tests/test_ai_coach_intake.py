import json

from fastapi.testclient import TestClient

from tests.test_ai_training_plans import SessionFactory, client_with_db, register_and_login, seed_exercises


def test_coach_intake_requires_required_fields_before_generating_plan(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "intake@example.com", "intake_user")

    intake_response = client.get("/ai/coach/intake", headers={"Authorization": f"Bearer {token}"})
    generate_response = client.post("/ai/coach/intake/generate-plan", headers={"Authorization": f"Bearer {token}"})

    assert intake_response.status_code == 200
    assert intake_response.json()["ready_for_plan"] is False
    assert intake_response.json()["missing_required_fields"] == ["goal", "level", "days_per_week", "session_duration_minutes"]
    assert generate_response.status_code == 422


def test_coach_intake_redacts_unacknowledged_sensitive_message(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "sensitive@example.com", "sensitive_user")

    response = client.post(
        "/ai/coach/intake/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "Quiero hipertrofia, soy principiante, 3 dias, 60 minutos, pero tengo dolor de rodilla",
            "sensitive_data_acknowledged": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ready_for_plan"] is True
    assert data["sensitive_data_acknowledged"] is False
    assert data["safety_warning"]
    assert data["intake_summary"]["goal"] == "hypertrophy"
    assert "physical_limitations" not in data["intake_summary"]
    assert "dolor de rodilla" not in json.dumps(data["recent_messages"]).lower()


def test_coach_intake_generates_training_plan_when_ready(
    client_with_db: tuple[TestClient, SessionFactory],
) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    token = register_and_login(client, "ready@example.com", "ready_user")

    intake_response = client.post(
        "/ai/coach/intake/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Hipertrofia, principiante, 3 dias, 60 minutos, tengo mancuernas", "sensitive_data_acknowledged": False},
    )
    plan_response = client.post("/ai/coach/intake/generate-plan", headers={"Authorization": f"Bearer {token}"})
    refreshed_intake = client.get("/ai/coach/intake", headers={"Authorization": f"Bearer {token}"})

    assert intake_response.status_code == 200
    assert intake_response.json()["ready_for_plan"] is True
    assert plan_response.status_code == 201
    plan = plan_response.json()
    assert plan["status"] == "draft"
    assert plan["days_per_week"] == 3
    assert len(plan["plan_payload"]["routines"]) == 3
    assert refreshed_intake.json()["status"] == "plan_generated"
