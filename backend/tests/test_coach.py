from fastapi.testclient import TestClient

from tests.test_ai_training_plans import SessionFactory, client_with_db, register_and_login, seed_exercises
from tests.test_coach_v2 import groq_v3_plan_response, use_fake_groq


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def complete_coach_profile(client: TestClient, token: str) -> dict:
    response = client.post(
        "/ai/coach/messages",
        headers=auth_headers(token),
        json={
            "message": "Tengo 29 anos, mido 180 cm, peso 80 kg. Soy hombre, quiero hipertrofia, nivel intermedio, 4 dias por semana, 60 min por sesion y gimnasio completo.",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": False,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_clean_coach_initial_state(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    token = register_and_login(client, "coach-clean-initial@example.com", "coach_clean_initial")

    response = client.get("/ai/coach", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "onboarding"
    assert body["ready_for_plan"] is False
    assert "personal_data_acknowledged" in body["missing_required_fields"]
    assert body["draft_plans"] == []
    assert body["accepted_plan"] is None
    assert "tokens" in body["privacy_notice"]


def test_clean_coach_message_updates_profile(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    token = register_and_login(client, "coach-clean-profile@example.com", "coach_clean_profile")

    body = complete_coach_profile(client, token)

    assert body["ready_for_plan"] is True
    assert body["phase"] == "ready_for_plan"
    assert body["missing_required_fields"] == []
    assert body["profile"]["goal"] == "hypertrophy"
    assert body["profile"]["biological_sex"] == "male"
    assert body["profile"]["age"] == 29
    assert body["profile"]["height_cm"] == 180
    assert body["profile"]["weight_kg"] == 80
    assert body["profile"]["days_per_week"] == 4
    assert body["profile"]["session_duration_minutes"] == 60
    assert "mancuernas" in body["profile"]["equipment"]


def test_clean_coach_does_not_store_limitations_without_ack(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    token = register_and_login(client, "coach-clean-sensitive@example.com", "coach_clean_sensitive")

    response = client.post(
        "/ai/coach/messages",
        headers=auth_headers(token),
        json={
            "message": "Tengo dolor de rodilla y molestias de espalda.",
            "personal_data_acknowledged": False,
            "sensitive_data_acknowledged": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["profile"]["physical_limitations"] is None


def test_clean_coach_generates_groq_draft(monkeypatch, client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    use_fake_groq(monkeypatch, groq_v3_plan_response(days=4))
    token = register_and_login(client, "coach-clean-groq@example.com", "coach_clean_groq")
    complete_coach_profile(client, token)

    response = client.post("/ai/coach/plans", headers=auth_headers(token))

    assert response.status_code == 201
    plan = response.json()
    assert plan["provider"] == "groq"
    assert plan["plan_payload"]["version"] == 3
    assert plan["plan_payload"]["coach_version"] == 1
    assert plan["input_summary"]["source"] == "coach_clean"

    state = client.get("/ai/coach", headers=auth_headers(token)).json()
    assert state["phase"] == "plan_draft"
    assert len(state["draft_plans"]) == 1
