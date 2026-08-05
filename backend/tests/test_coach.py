import json
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.test_ai_training_plans import SessionFactory, client_with_db, register_and_login, seed_exercises


class FakeGroqResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return self.body


def groq_chat_response(payload: dict) -> bytes:
    return json.dumps({"choices": [{"message": {"content": json.dumps(payload)}}]}).encode("utf-8")


def use_fake_groq_sequence(monkeypatch, responses: list[bytes]) -> None:
    monkeypatch.setenv("APP_AI_PROVIDER", "groq")
    monkeypatch.setenv("APP_AI_GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("APP_AI_GROQ_MODEL", "llama-3.3-70b-versatile")
    get_settings.cache_clear()
    queue = list(responses)

    def fake_urlopen(_request, timeout):
        if not queue:
            raise AssertionError("Unexpected Groq request")
        return FakeGroqResponse(queue.pop(0))

    monkeypatch.setattr("app.application.ai_provider.urlopen", fake_urlopen)


def use_fake_groq_http_error(monkeypatch, status_code: int) -> None:
    monkeypatch.setenv("APP_AI_PROVIDER", "groq")
    monkeypatch.setenv("APP_AI_GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("APP_AI_GROQ_MODEL", "llama-3.1-8b-instant")
    get_settings.cache_clear()

    def fake_urlopen(_request, timeout):
        raise HTTPError("https://api.groq.com/openai/v1/chat/completions", status_code, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr("app.application.ai_provider.urlopen", fake_urlopen)


def interview_response(*, include_sensitive: bool = False) -> bytes:
    updates = {
        "goal": "hypertrophy",
        "biological_sex": "male",
        "age": 29,
        "height_cm": 180,
        "weight_kg": 80,
        "experience_level": "intermediate",
        "days_per_week": 4,
        "session_duration_minutes": 60,
        "equipment": ["mancuernas", "barra", "banco", "polea", "maquina", "peso corporal"],
        "priorities": ["pecho", "espalda"],
        "available_weekdays": ["lunes", "martes", "jueves", "viernes"],
        "tracking_method": "Registrara cargas, repeticiones y RIR en Zenith.",
    }
    if include_sensitive:
        updates["physical_limitations"] = "Molestia de rodilla con prensa."
    return groq_chat_response(
        {
            "assistant_message": "Perfecto. Ya tengo lo imprescindible para preparar una vista previa seria. Antes de generarla, si quieres podemos afinar sueño, nutrición y marcas principales.",
            "profile_updates": updates,
            "known_facts": ["Objetivo principal: hipertrofia", "Nivel intermedio", "Entrena 4 dias por semana"],
            "missing_critical": [],
            "missing_useful": ["sueno", "nutricion", "marcas principales"],
            "estimated_fields": ["volumen inicial conservador"],
            "misunderstanding_corrections": [],
            "safety_flags": [],
            "ready_for_plan": True,
            "next_questions": ["Si quieres afinar mas: ¿como duermes y que marcas manejas en movimientos principales?"],
        }
    )


def evidence_query_response() -> bytes:
    return groq_chat_response(
        {
            "evidence_queries": [
                "resistance training hypertrophy volume systematic review meta analysis",
                "proximity to failure resistance training hypertrophy meta analysis",
                "protein intake resistance training muscle hypertrophy position stand",
            ],
            "rationale": ["Volumen, fallo y proteina son decisiones clave del plan."],
        }
    )


def fake_evidence() -> dict:
    return {
        "search_queries": ["resistance training hypertrophy volume systematic review meta analysis"],
        "used_references": [
            {
                "source": "pubmed",
                "title": "Resistance training volume enhances muscle hypertrophy",
                "authors": ["Schoenfeld BJ"],
                "year": "2017",
                "journal": "Journal of Sports Sciences",
                "pmid": "27433992",
                "doi": "10.1080/example",
                "abstract": "Systematic review on training volume and hypertrophy.",
                "query": "resistance training hypertrophy volume systematic review meta analysis",
                "evidence_level": "solid",
            }
        ],
        "limitations": ["PubMed mock."],
        "errors": [],
        "privacy": {"personal_data_sent_to_pubmed": False, "queries_are_neutral": True, "profile_sent_to_pubmed": False},
    }


def sensitive_interview_response() -> bytes:
    return groq_chat_response(
        {
            "assistant_message": "Antes de tratar dolor o lesiones necesito que confirmes el aviso medico. No voy a diagnosticar.",
            "profile_updates": {"physical_limitations": "Dolor de rodilla"},
            "known_facts": [],
            "missing_critical": ["goal", "biological_sex", "age", "height_cm", "weight_kg", "experience_level", "days_per_week", "session_duration_minutes", "equipment"],
            "missing_useful": [],
            "estimated_fields": [],
            "misunderstanding_corrections": [],
            "safety_flags": ["dolor requiere precaucion"],
            "ready_for_plan": False,
            "next_questions": ["Confirma el aviso medico si quieres que use esa limitacion para adaptar el plan."],
        }
    )


def plan_response(*, days: int = 4) -> bytes:
    routines = []
    for day in range(1, days + 1):
        routines.append(
            {
                "day": day,
                "name": f"Sesion IA {day}",
                "focus": "hipertrofia",
                "description": "Sesion creada por el Coach IA.",
                "target_duration_minutes": 60,
                "session_role": "primary_training",
                "exercises": [
                    {
                        "exercise_id": None,
                        "exercise_name": f"Press maquina IA {day}",
                        "description": "Ejercicio principal de empuje en maquina.",
                        "technique_notes": "Tecnica estable, recorrido controlado y sin dolor.",
                        "difficulty": "intermediate",
                        "equipment": ["maquina"],
                        "slot": "main_lift",
                        "role": "principal",
                        "movement_pattern": "press",
                        "primary_muscle": "Pecho",
                        "secondary_muscles": ["Triceps"],
                        "target_sets": 3,
                        "target_reps_min": 8,
                        "target_reps_max": 12,
                        "target_rpe": "8",
                        "target_rir": 2,
                        "rest_seconds": 120,
                        "reason": "Permite progresar con fatiga controlada.",
                        "progression_hint": "Sube repeticiones antes de carga.",
                    }
                ],
            }
        )
    payload = {
        "version": 3,
        "generated_by": {"provider": "groq", "model": "llama-3.3-70b-versatile", "mode": "coach_plan", "backend_validated": False},
        "program_blueprint": {"split_id": "upper_lower_4", "split_name": "Upper/lower", "horizon_weeks": 10, "strategy": "Volumen moderado y progresion doble."},
        "coach_rationale": {"summary": "Plan individualizado para hipertrofia con volumen recuperable.", "why_this_split": "Frecuencia 2", "why_this_volume": "Punto inicial razonable", "why_these_exercises": "Alta estabilidad", "tradeoffs": []},
        "exercise_resolution": {"summary": {}, "items": []},
        "weekly_schedule": [{"day": day, "routine_key": f"day_{day}", "name": f"Sesion IA {day}", "focus": "hipertrofia", "target_duration_minutes": 60, "intent": "Progresar con buena tecnica."} for day in range(1, days + 1)],
        "volume_by_muscle": {"Pecho": {"direct_sets": 12, "indirect_sets": 0, "target_range": [8, 14], "priority": True, "status": "in_range"}},
        "progression_model": {"type": "double_progression", "block_weeks": 10, "load_rule": "Sube carga al completar el rango con RIR objetivo.", "rep_rule": "Primero reps, luego carga.", "rir_targets_by_week": [{"week": 1, "rir": 3}], "deload_rule": "Descarga si cae rendimiento y sube fatiga."},
        "routines": routines,
        "validation_report": {"status": "passed", "checks": [], "warnings": []},
        "acceptance_effects": {"will_create_private_exercises": True, "private_exercise_count": 0, "will_create_routines": True, "routine_count": days, "requires_user_acceptance": True},
        "coach_report": {"user_data_summary": "Intermedio orientado a hipertrofia.", "assumptions": ["Volumen inicial moderado"], "measurable_goals": ["Progresar reps o carga semanalmente"], "split_justification": "Upper/lower por frecuencia y recuperacion.", "weekly_calendar": [], "training_tables_summary": "Ver rutinas.", "progression_system": "Doble progresion.", "warmup": "Series de aproximacion.", "fatigue_and_deload": "Descargar si empeoran indicadores.", "tracking_template": "Carga, reps, RIR y dolor.", "nutrition_and_recovery": "Proteina y superavit moderado.", "substitutions": [], "mistakes_to_avoid": ["Entrenar con dolor creciente"], "scientific_references": [{"title": "Resistance training volume enhances muscle hypertrophy", "year": "2017", "evidence_level": "moderate"}], "next_review_questions": ["Enviame registros semanales."]},
        "explanation": "Vista previa generada por Coach.",
        "risk_notes": "No sustituye consejo medico.",
        "confidence": "medium",
    }
    return groq_chat_response(payload)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def complete_coach_profile(client: TestClient, token: str) -> dict:
    response = client.post(
        "/ai/coach/messages",
        headers=auth_headers(token),
        json={
            "message": "Tengo 29 anos, 180 cm, 80 kg. Soy hombre, quiero hipertrofia, nivel intermedio, 4 dias, 60 min y gimnasio completo.",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": False,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_coach_initial_state(client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    token = register_and_login(client, "coach-initial@example.com", "coach_initial")

    response = client.get("/ai/coach", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "onboarding"
    assert body["ready_for_plan"] is False
    assert "personal_data_acknowledged" in body["missing_critical"]
    assert body["draft_plans"] == []
    assert body["accepted_plan"] is None
    assert "tokens" in body["privacy_notice"]


def test_coach_message_uses_groq_and_updates_profile(monkeypatch, client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    use_fake_groq_sequence(monkeypatch, [interview_response()])
    token = register_and_login(client, "coach-profile@example.com", "coach_profile")

    body = complete_coach_profile(client, token)

    assert body["ready_for_plan"] is True
    assert body["phase"] == "ready_for_plan"
    assert body["missing_critical"] == []
    assert body["profile"]["goal"] == "hypertrophy"
    assert body["profile"]["biological_sex"] == "male"
    assert body["profile"]["age"] == 29
    assert body["profile"]["height_cm"] == 180
    assert body["profile"]["weight_kg"] == 80
    assert body["profile"]["days_per_week"] == 4
    assert body["profile"]["session_duration_minutes"] == 60
    assert "mancuernas" in body["profile"]["equipment"]
    assert body["known_facts"]


def test_coach_does_not_store_limitations_without_ack(monkeypatch, client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    use_fake_groq_sequence(monkeypatch, [sensitive_interview_response()])
    token = register_and_login(client, "coach-sensitive@example.com", "coach_sensitive")

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
    assert response.json()["safety_flags"] == ["dolor requiere precaucion"]


def test_coach_message_returns_readable_error_when_groq_fails(monkeypatch, client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    use_fake_groq_sequence(monkeypatch, [b"not-json"])
    token = register_and_login(client, "coach-error@example.com", "coach_error")

    response = client.post(
        "/ai/coach/messages",
        headers=auth_headers(token),
        json={
            "message": "acepto el aviso, quiero un entrenamiento de fuerza",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Groq returned invalid JSON."


def test_coach_message_returns_groq_status_when_provider_forbidden(monkeypatch, client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, _session_factory = client_with_db
    use_fake_groq_http_error(monkeypatch, 403)
    token = register_and_login(client, "coach-forbidden@example.com", "coach_forbidden")

    response = client.post(
        "/ai/coach/messages",
        headers=auth_headers(token),
        json={
            "message": "acepto el aviso, quiero un entrenamiento de fuerza",
            "personal_data_acknowledged": True,
            "sensitive_data_acknowledged": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Groq request failed with status 403."


def test_coach_generates_groq_plan_draft(monkeypatch, client_with_db: tuple[TestClient, SessionFactory]) -> None:
    client, session_factory = client_with_db
    seed_exercises(session_factory)
    use_fake_groq_sequence(monkeypatch, [interview_response(), evidence_query_response(), plan_response(days=4)])
    monkeypatch.setattr("app.application.coach_service.evidence_search_service.search_many", lambda _queries: fake_evidence())
    token = register_and_login(client, "coach-groq@example.com", "coach_groq")
    complete_coach_profile(client, token)

    response = client.post("/ai/coach/plan-drafts", headers=auth_headers(token))

    assert response.status_code == 201
    plan = response.json()
    assert plan["provider"] == "groq"
    assert plan["plan_payload"]["version"] == 3
    assert plan["plan_payload"]["source"] == "coach"
    assert plan["plan_payload"]["schema_version"] == 1
    assert plan["input_summary"]["created_by"] == "coach"
    assert "coach_report" in plan["plan_payload"]
    assert plan["plan_payload"]["evidence"]["used_references"][0]["pmid"] == "27433992"
    assert plan["input_summary"]["evidence"]["privacy"]["personal_data_sent_to_pubmed"] is False

    state = client.get("/ai/coach", headers=auth_headers(token)).json()
    assert state["phase"] == "plan_draft"
    assert len(state["draft_plans"]) == 1
