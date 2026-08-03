import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.test_ai_training_plans import SessionFactory, client_with_db, register_and_login, seed_exercises


def ollama_v3_plan_response(*, days: int = 3, include_avoided: bool = False) -> bytes:
    exercise_names = [
        "Press inclinado con mancuernas",
        "Remo pecho apoyado con mancuernas",
        "Sentadilla goblet",
        "Jalon al pecho",
        "Hip thrust con barra",
        "Elevaciones laterales",
        "Curl femoral tumbado",
    ]
    if include_avoided:
        exercise_names[0] = "Peso muerto"
    routines = []
    for day in range(1, days + 1):
        name = exercise_names[(day - 1) % len(exercise_names)]
        muscle = "Pecho" if "Press" in name else "Espalda" if "Remo" in name or "Jalon" in name else "Piernas"
        routines.append(
            {
                "day": day,
                "name": f"Sesion IA {day}",
                "focus": "full_body",
                "description": "Sesion creada por entrenador IA.",
                "target_duration_minutes": 60,
                "session_role": "primary_training",
                "exercises": [
                    {
                        "exercise_id": None,
                        "exercise_name": name,
                        "description": f"Ejercicio para {muscle.lower()} dentro del plan.",
                        "technique_notes": "Mantener tecnica estable, rango controlado y parar si aparece dolor.",
                        "difficulty": "intermediate",
                        "equipment": ["Mancuernas", "Banco"] if "mancuernas" in name.lower() else ["Maquina"],
                        "slot": "main_lift",
                        "role": "principal",
                        "movement_pattern": "compound_pattern",
                        "primary_muscle": muscle,
                        "secondary_muscles": ["Core"],
                        "target_sets": 3,
                        "target_reps_min": 8,
                        "target_reps_max": 12,
                        "target_rpe": "8",
                        "target_rir": 2,
                        "rest_seconds": 120,
                        "reason": "Seleccionado por la IA para cubrir el rol principal del dia y el volumen semanal.",
                        "progression_hint": "Sube reps dentro del rango antes de subir carga.",
                    }
                ],
            }
        )
    payload = {
        "version": 3,
        "generated_by": {"provider": "ollama", "model": "llama3.2", "mode": "ai_personal_trainer", "backend_validated": False},
        "program_blueprint": {
            "split_id": "full_body_3",
            "split_name": "Full body IA",
            "horizon_weeks": 6,
            "strategy": "Programa por patrones con volumen distribuido.",
            "weekly_structure": [],
            "weekly_volume_targets": {"Pecho": {"target_sets": 9, "range": [6, 12], "priority": False}},
        },
        "coach_rationale": {
            "summary": "Plan creado por Ollama con arquitectura previa.",
            "why_this_split": "Distribuye los patrones en la semana.",
            "why_this_volume": "Mantiene volumen recuperable.",
            "why_these_exercises": "Cada ejercicio cubre un rol del programa.",
            "tradeoffs": [],
        },
        "exercise_resolution": {"summary": {}, "items": []},
        "weekly_schedule": [{"day": day, "routine_key": f"day_{day}", "name": f"Sesion IA {day}", "focus": "full_body", "target_duration_minutes": 60, "intent": "Entrenar patrones basicos."} for day in range(1, days + 1)],
        "volume_by_muscle": {"Pecho": {"direct_sets": 9, "indirect_sets": 0, "target_range": [6, 12], "priority": False, "status": "in_range"}},
        "progression_model": {
            "type": "double_progression",
            "block_weeks": 6,
            "load_rule": "Sube carga al completar el rango con RIR objetivo.",
            "rep_rule": "Sube reps antes de carga.",
            "rir_targets_by_week": [{"week": 1, "rir": 3, "intent": "adaptacion"}],
            "deload_rule": "Reduce volumen si hay fatiga alta.",
        },
        "routines": routines,
        "validation_report": {"status": "passed", "checks": [], "warnings": []},
        "acceptance_effects": {"will_create_private_exercises": True, "private_exercise_count": 0, "will_create_routines": True, "routine_count": days, "requires_user_acceptance": True},
        "explanation": "Plan V3 creado por Ollama.",
        "risk_notes": "No sustituye consejo medico.",
        "confidence": "medium",
    }
    return json.dumps({"response": json.dumps(payload)}).encode("utf-8")


def groq_v3_plan_response(*, days: int = 3) -> bytes:
    ollama_response = json.loads(ollama_v3_plan_response(days=days).decode("utf-8"))
    payload = json.loads(ollama_response["response"])
    payload["generated_by"] = {"provider": "groq", "model": "llama-3.3-70b-versatile", "mode": "ai_personal_trainer", "backend_validated": False}
    payload["explanation"] = "Plan V3 creado por Groq."
    return json.dumps({"choices": [{"message": {"content": json.dumps(payload)}}]}).encode("utf-8")


class FakeOllamaResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return self.body


def use_fake_ollama(monkeypatch, body: bytes) -> None:
    monkeypatch.setenv("APP_AI_PROVIDER", "ollama")
    monkeypatch.setenv("APP_AI_OLLAMA_MODEL", "llama3.2")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", lambda _request, timeout: FakeOllamaResponse(body))


def use_fake_groq(monkeypatch, body: bytes) -> None:
    monkeypatch.setenv("APP_AI_PROVIDER", "groq")
    monkeypatch.setenv("APP_AI_GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("APP_AI_GROQ_MODEL", "llama-3.3-70b-versatile")
    get_settings.cache_clear()
    monkeypatch.setattr("app.application.ai_provider.urlopen", lambda _request, timeout: FakeOllamaResponse(body))


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
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch, goal_text: str, goal: str
) -> None:
    use_fake_ollama(monkeypatch, ollama_v3_plan_response(days=3))
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
    assert plan["provider"] == "ollama"
    assert plan["plan_payload"]["version"] == 3
    assert plan["plan_payload"]["generated_by"]["backend_validated"] is True
    assert plan["plan_payload"]["exercise_resolution"]["summary"]["ai_generated_pending_count"] == 3
    assert len(plan["plan_payload"]["routines"]) == 3
    get_settings.cache_clear()


def test_coach_v2_requires_ollama_for_v3_generation(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory, count=8)
    token = register_and_login(client, "coach-v2-no-ollama@example.com", "coach_v2_no_ollama")

    client.post(
        "/ai/coach/v2/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "acepto, objetivo hipertrofia, femenino, 31 anos, 165 cm, 62 kg, intermedio, 3 dias, 60 minutos, gimnasio comercial",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": False,
        },
    )
    response = client.post("/ai/coach/v2/generate-plan", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422
    assert "ollama" in response.json()["detail"].lower()


def test_coach_v2_generates_v3_plan_with_groq(client_with_db: tuple[TestClient, SessionFactory], monkeypatch) -> None:
    use_fake_groq(monkeypatch, groq_v3_plan_response(days=3))
    client, session_factory = client_with_db
    seed_exercises(session_factory, count=8)
    token = register_and_login(client, "coach-v2-groq@example.com", "coach_v2_groq")

    client.post(
        "/ai/coach/v2/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "acepto, objetivo hipertrofia, femenino, 31 anos, 165 cm, 62 kg, intermedio, 3 dias, 60 minutos, gimnasio comercial",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": False,
        },
    )
    response = client.post("/ai/coach/v2/generate-plan", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201
    plan = response.json()
    assert plan["provider"] == "groq"
    assert plan["input_summary"]["ai_provider"]["external_data_sent"] is True
    assert plan["plan_payload"]["version"] == 3
    assert plan["plan_payload"]["generated_by"]["provider"] == "groq"
    assert plan["plan_payload"]["generated_by"]["backend_validated"] is True
    get_settings.cache_clear()


def test_coach_v2_accepts_v3_plan_and_creates_pending_exercises_as_private(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    use_fake_ollama(monkeypatch, ollama_v3_plan_response(days=3))
    client, session_factory = client_with_db
    seed_exercises(session_factory, count=8)
    token = register_and_login(client, "coach-v2-private-exercises@example.com", "coach_v2_private_exercises")

    client.post(
        "/ai/coach/v2/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "acepto, objetivo hipertrofia, masculino, 34 anos, 178 cm, 82 kg, intermedio, 3 dias, 60 minutos, gimnasio comercial",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": False,
        },
    )
    plan = client.post("/ai/coach/v2/generate-plan", headers={"Authorization": f"Bearer {token}"}).json()
    before_accept = client.get("/exercises", headers={"Authorization": f"Bearer {token}"}).json()

    accepted = client.post(f"/ai/training-plans/{plan['id']}/accept", headers={"Authorization": f"Bearer {token}"})
    after_accept = client.get("/exercises", headers={"Authorization": f"Bearer {token}"}).json()

    assert accepted.status_code == 200
    accepted_payload = accepted.json()["plan_payload"]
    assert len(accepted_payload["created_private_exercise_ids"]) == 3
    assert len(after_accept) == len(before_accept) + 3
    created_ids = set(accepted_payload["created_private_exercise_ids"])
    created = [exercise for exercise in after_accept if exercise["id"] in created_ids]
    assert len(created) == 3
    assert all(exercise["is_global"] is False for exercise in created)
    get_settings.cache_clear()


def test_coach_v2_rejects_ollama_plan_with_avoided_exercise(
    client_with_db: tuple[TestClient, SessionFactory], monkeypatch
) -> None:
    use_fake_ollama(monkeypatch, ollama_v3_plan_response(days=3, include_avoided=True))
    client, session_factory = client_with_db
    seed_exercises(session_factory, count=8)
    token = register_and_login(client, "coach-v2-avoided@example.com", "coach_v2_avoided")

    client.post(
        "/ai/coach/v2/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": "acepto, objetivo hipertrofia, masculino, 34 anos, 178 cm, 82 kg, intermedio, 3 dias, 60 minutos, gimnasio comercial, sin peso muerto",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": False,
        },
    )
    response = client.post("/ai/coach/v2/generate-plan", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422
    get_settings.cache_clear()


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
