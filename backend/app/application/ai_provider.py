import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings

MAX_TEXT_LENGTH = 600
VALID_CONFIDENCE = {"low", "medium", "high"}


class AiProviderError(Exception):
    pass


@dataclass(frozen=True)
class AiProviderContext:
    suggestion_type: str
    input_summary: dict[str, Any]
    recommendation: str
    explanation: str
    apply_payload: dict[str, Any]


@dataclass(frozen=True)
class AiProviderResult:
    recommendation: str
    explanation: str
    risk_notes: str | None
    confidence: str
    provider: str
    model: str | None
    external_data_sent: bool
    fallback_used: bool = False


@dataclass(frozen=True)
class AiTrainingPlanProviderContext:
    goal: str
    level: str
    days_per_week: int
    session_duration_minutes: int
    available_equipment: list[str]
    priorities: list[str]
    has_physical_limitations: bool
    routine_count: int
    exercises_per_routine: list[int]
    base_explanation: str
    base_risk_notes: str | None
    modification_instruction: str | None = None
    exercise_catalog: list[dict[str, Any]] | None = None
    physical_limitations: str | None = None
    validation_errors: list[str] | None = None


@dataclass(frozen=True)
class AiTrainingPlanProviderResult:
    explanation: str
    risk_notes: str | None
    confidence: str
    provider: str
    model: str | None
    external_data_sent: bool
    fallback_used: bool = False


@dataclass(frozen=True)
class AiTrainingPlanStructureProviderResult:
    plan_payload: dict[str, Any]
    explanation: str
    risk_notes: str | None
    confidence: str
    provider: str
    model: str | None
    external_data_sent: bool
    fallback_used: bool = False


@dataclass(frozen=True)
class AiSessionSummaryProviderContext:
    input_summary: dict[str, Any]
    summary: str
    improvements: list[str]
    drops: list[str]
    warnings: list[str]
    next_recommendation: str


@dataclass(frozen=True)
class AiSessionSummaryProviderResult:
    summary: str
    improvements: list[str]
    drops: list[str]
    warnings: list[str]
    next_recommendation: str
    provider: str
    model: str | None
    external_data_sent: bool
    fallback_used: bool = False


@dataclass(frozen=True)
class CoachInterviewProviderContext:
    profile: dict[str, Any]
    interview_state: dict[str, Any]
    recent_messages: list[dict[str, Any]]
    user_message: str | None
    personal_data_acknowledged: bool
    sensitive_data_acknowledged: bool
    missing_critical: list[str]
    missing_useful: list[str]


@dataclass(frozen=True)
class CoachInterviewProviderResult:
    assistant_message: str
    profile_updates: dict[str, Any]
    known_facts: list[str]
    missing_critical: list[str]
    missing_useful: list[str]
    estimated_fields: list[str]
    misunderstanding_corrections: list[str]
    safety_flags: list[str]
    ready_for_plan: bool
    next_questions: list[str]
    provider: str
    model: str | None
    external_data_sent: bool
    fallback_used: bool = False


class InternalAiProvider:
    provider = "internal"
    model = "rules"
    external_data_sent = False

    def build_explanation(self, context: AiProviderContext) -> AiProviderResult:
        return AiProviderResult(
            recommendation=context.recommendation,
            explanation=context.explanation,
            risk_notes="Si notas dolor, tecnica peor o fatiga inusual, no apliques el cambio y registra una sesion mas suave.",
            confidence=self._confidence_for(context.suggestion_type),
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def build_training_plan_text(self, context: AiTrainingPlanProviderContext) -> AiTrainingPlanProviderResult:
        return AiTrainingPlanProviderResult(
            explanation=context.base_explanation,
            risk_notes=context.base_risk_notes,
            confidence="medium",
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def build_session_summary_text(self, context: AiSessionSummaryProviderContext) -> AiSessionSummaryProviderResult:
        return AiSessionSummaryProviderResult(
            summary=context.summary,
            improvements=context.improvements,
            drops=context.drops,
            warnings=context.warnings,
            next_recommendation=context.next_recommendation,
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def build_coach_interview_response(self, context: CoachInterviewProviderContext) -> CoachInterviewProviderResult:
        missing = context.missing_critical
        question = "Cuéntame tu objetivo, experiencia, disponibilidad, equipo y cualquier preferencia importante."
        if missing:
            question = "Para empezar bien necesito algunos datos: objetivo, edad/sexo, altura/peso, nivel, dias, duracion y equipamiento."
        return CoachInterviewProviderResult(
            assistant_message=question,
            profile_updates={},
            known_facts=list(context.interview_state.get("known_facts") or []),
            missing_critical=missing,
            missing_useful=context.missing_useful,
            estimated_fields=list(context.interview_state.get("estimated_fields") or []),
            misunderstanding_corrections=[],
            safety_flags=[],
            ready_for_plan=not missing,
            next_questions=[question],
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def _confidence_for(self, suggestion_type: str) -> str:
        if suggestion_type in {"increase_weight", "increase_rest"}:
            return "high"
        if suggestion_type in {"reduce_volume", "change_reps", "deload_recommended", "exercise_swap", "routine_goal_adjustment"}:
            return "medium"
        return "low"

class OllamaAiProvider:
    provider = "ollama"
    external_data_sent = False

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ai_ollama_base_url.rstrip("/")
        self.model = settings.ai_ollama_model
        self.timeout_seconds = settings.ai_timeout_seconds

    def build_explanation(self, context: AiProviderContext) -> AiProviderResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._prompt(context),
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (OSError, URLError) as error:
            raise AiProviderError("Ollama request failed.") from error

        try:
            parsed = json.loads(raw)
            model_response = json.loads(parsed.get("response", ""))
        except (TypeError, ValueError) as error:
            raise AiProviderError("Ollama returned invalid JSON.") from error

        return self._parse_model_response(model_response)

    def build_training_plan_text(self, context: AiTrainingPlanProviderContext) -> AiTrainingPlanProviderResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._training_plan_prompt(context),
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (OSError, URLError) as error:
            raise AiProviderError("Ollama request failed.") from error

        try:
            parsed = json.loads(raw)
            model_response = json.loads(parsed.get("response", ""))
        except (TypeError, ValueError) as error:
            raise AiProviderError("Ollama returned invalid JSON.") from error

        return self._parse_training_plan_response(model_response)

    def build_training_plan_structure(self, context: AiTrainingPlanProviderContext) -> AiTrainingPlanStructureProviderResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._training_plan_structure_prompt(context),
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (OSError, URLError) as error:
            raise AiProviderError("Ollama request failed.") from error

        try:
            parsed = json.loads(raw)
            model_response = json.loads(parsed.get("response", ""))
        except (TypeError, ValueError) as error:
            raise AiProviderError("Ollama returned invalid JSON.") from error

        return self._parse_training_plan_structure_response(model_response)

    def build_session_summary_text(self, context: AiSessionSummaryProviderContext) -> AiSessionSummaryProviderResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._session_summary_prompt(context),
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (OSError, URLError) as error:
            raise AiProviderError("Ollama request failed.") from error

        try:
            parsed = json.loads(raw)
            model_response = json.loads(parsed.get("response", ""))
        except (TypeError, ValueError) as error:
            raise AiProviderError("Ollama returned invalid JSON.") from error

        return self._parse_session_summary_response(model_response)

    def build_coach_interview_response(self, context: CoachInterviewProviderContext) -> CoachInterviewProviderResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._coach_interview_prompt(context),
        }
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (OSError, URLError) as error:
            raise AiProviderError("Ollama request failed.") from error

        try:
            parsed = json.loads(raw)
            model_response = json.loads(parsed.get("response", ""))
        except (TypeError, ValueError) as error:
            raise AiProviderError("Ollama returned invalid JSON.") from error

        return self._parse_coach_interview_response(model_response)

    def _prompt(self, context: AiProviderContext) -> str:
        safe_context = {
            "suggestion_type": context.suggestion_type,
            "metrics": context.input_summary.get("metrics", {}),
            "analysis_window": context.input_summary.get("analysis_window", {}),
            "planned_exercise": context.input_summary.get("planned_exercise", {}),
            "planned_change": context.input_summary.get("planned_change", {}),
            "rule_triggered": context.input_summary.get("rule_triggered"),
            "recommendation": context.recommendation,
            "explanation": context.explanation,
        }
        return (
            "Eres un entrenador de fuerza. Devuelve solo JSON valido con keys: "
            "recommendation, explanation, risk_notes, confidence. "
            "confidence debe ser low, medium o high. No propongas cambios distintos; el cambio ya fue validado. "
            "No menciones datos personales. Contexto estructurado: "
            f"{json.dumps(safe_context, ensure_ascii=False)}"
        )

    def _training_plan_prompt(self, context: AiTrainingPlanProviderContext) -> str:
        safe_context = {
            "goal": context.goal,
            "level": context.level,
            "days_per_week": context.days_per_week,
            "session_duration_minutes": context.session_duration_minutes,
            "available_equipment": context.available_equipment,
            "priorities": context.priorities,
            "has_physical_limitations": context.has_physical_limitations,
            "routine_count": context.routine_count,
            "exercises_per_routine": context.exercises_per_routine,
            "base_explanation": context.base_explanation,
            "base_risk_notes": context.base_risk_notes,
            "modification_instruction": context.modification_instruction,
        }
        return (
            "Eres un entrenador de fuerza. Devuelve solo JSON valido con keys: "
            "explanation, risk_notes, confidence. confidence debe ser low, medium o high. "
            "No cambies ejercicios, series, repeticiones, descansos ni estructura; el plan ya fue validado por backend. "
            "No menciones datos personales ni diagnosticos. Contexto estructurado: "
            f"{json.dumps(safe_context, ensure_ascii=False)}"
        )

    def _training_plan_structure_prompt(self, context: AiTrainingPlanProviderContext) -> str:
        safe_context = {
            "goal": context.goal,
            "level": context.level,
            "days_per_week": context.days_per_week,
            "session_duration_minutes": context.session_duration_minutes,
            "available_equipment": context.available_equipment,
            "priorities": context.priorities,
            "physical_limitations": context.physical_limitations,
            "modification_instruction": context.modification_instruction,
            "validation_errors_to_fix": context.validation_errors or [],
        }
        return (
            "Eres el entrenador personal de Zenith. Disena el mejor programa posible para el usuario, sin limitarte a una base de datos de ejercicios. "
            "Devuelve SOLO JSON valido. No diagnostiques, no prometas resultados absolutos y no incluyas datos personales no aportados. "
            "El JSON debe ser plan_payload v3 y tener keys: version, generated_by, program_blueprint, coach_rationale, exercise_resolution, "
            "weekly_schedule, volume_by_muscle, progression_model, routines, validation_report, acceptance_effects, coach_report, explanation, risk_notes, confidence. "
            f"version debe ser 3. generated_by.provider debe ser {self.provider}. confidence debe ser low, medium o high. "
            "Primero disena la arquitectura del programa: split, volumen semanal por musculo, roles por dia y progresion. Luego elige ejercicios. "
            "No uses ejercicios que el usuario pidio evitar en priorities con formato 'evitar ...'. "
            "routines debe tener exactamente days_per_week elementos. Cada routine debe tener: day, name, focus, description, target_duration_minutes, session_role, exercises. "
            "Cada exercise debe tener: exercise_id null, exercise_name, description, technique_notes, difficulty, equipment, slot, role, movement_pattern, "
            "primary_muscle, secondary_muscles, target_sets, target_reps_min, target_reps_max, target_rpe, target_rir, rest_seconds, reason, progression_hint. "
            "Rangos seguros: target_sets 1-8, reps 1-30, target_rpe 6-9, target_rir 0-4, rest_seconds 45-300. "
            "Usa compuestos antes que accesorios, reparte volumen por semana, justifica cada ejercicio y declara que ejercicios nuevos se crearan solo al aceptar. "
            "coach_report debe ser un informe profesional con keys: user_data_summary, assumptions, measurable_goals, split_justification, weekly_calendar, "
            "training_tables_summary, progression_system, warmup, fatigue_and_deload, tracking_template, nutrition_and_recovery, substitutions, mistakes_to_avoid, "
            "scientific_references, next_review_questions. scientific_references debe contener solo referencias reales conocidas y verificables; si no estas seguro, "
            "indica evidencia no concluyente en vez de inventar autores, DOI, PMID o enlaces. Distingue evidence_level solid, moderate o practical. "
            "Contexto estructurado: "
            f"{json.dumps(safe_context, ensure_ascii=False)}"
        )

    def _session_summary_prompt(self, context: AiSessionSummaryProviderContext) -> str:
        safe_context = {
            "input_summary": context.input_summary,
            "base_summary": context.summary,
            "base_improvements": context.improvements,
            "base_drops": context.drops,
            "base_warnings": context.warnings,
            "base_next_recommendation": context.next_recommendation,
        }
        return (
            "Eres un entrenador de fuerza. Devuelve solo JSON valido con keys: "
            "summary, improvements, drops, warnings, next_recommendation. "
            "improvements, drops y warnings deben ser arrays de strings. "
            "No propongas cambios directos en rutinas ni sesiones. No menciones datos personales ni notas privadas. "
            "Contexto estructurado: "
            f"{json.dumps(safe_context, ensure_ascii=False)}"
        )

    def _coach_interview_prompt(self, context: CoachInterviewProviderContext) -> str:
        safe_context = {
            "profile": context.profile,
            "interview_state": context.interview_state,
            "recent_messages": context.recent_messages[-10:],
            "latest_user_message": context.user_message,
            "personal_data_acknowledged": context.personal_data_acknowledged,
            "sensitive_data_acknowledged": context.sensitive_data_acknowledged,
            "missing_critical": context.missing_critical,
            "missing_useful": context.missing_useful,
        }
        allowed_updates = [
            "goal",
            "secondary_goal",
            "biological_sex",
            "age",
            "height_cm",
            "weight_kg",
            "experience_level",
            "training_age_months",
            "days_per_week",
            "session_duration_minutes",
            "equipment",
            "priorities",
            "preferred_exercises",
            "avoided_exercises",
            "physical_limitations",
            "sleep_quality",
            "stress_level",
            "current_fatigue",
            "available_weekdays",
            "training_location",
            "current_routine",
            "recent_results",
            "main_lifts",
            "lagging_muscles",
            "well_developed_muscles",
            "nutrition_current",
            "willing_to_track_nutrition",
            "timeline_goal",
            "weeks_with_limited_training",
            "tracking_method",
            "body_fat_percent",
        ]
        return (
            "Actua como un equipo multidisciplinar: especialista en ciencias del deporte, entrenador de hipertrofia/fuerza, "
            "experto en biomecanica, fisiologia, recuperacion y prevencion de lesiones, e investigador critico. "
            "Tu tarea ahora es SOLO entrevistar. No generes programa ni tablas de entrenamiento hasta que ready_for_plan sea true y el usuario pida la vista previa. "
            "Conversa de forma natural, profesional y clara. Pregunta por bloques manejables, no por campos sueltos. No repitas datos ya conocidos. "
            "Corrige malentendidos si el usuario aclara algo. Distingue datos imprescindibles, utiles y estimables. "
            "Si hay dolor, lesion, limitacion o antecedente medico, no diagnostiques; recomienda valoracion sanitaria si hay dolor agudo, creciente, persistente o sintomas preocupantes. "
            "No guardes ni devuelvas physical_limitations si sensitive_data_acknowledged=false; en ese caso pide confirmacion del aviso medico antes de tratar esos datos. "
            "No incluyas email, username, tokens, credenciales, notas privadas ni historial completo. "
            "Devuelve SOLO JSON valido con keys: assistant_message, profile_updates, known_facts, missing_critical, missing_useful, "
            "estimated_fields, misunderstanding_corrections, safety_flags, ready_for_plan, next_questions. "
            "profile_updates solo puede incluir estas keys: "
            f"{json.dumps(allowed_updates, ensure_ascii=False)}. "
            "missing_critical debe contener solo datos imprescindibles que falten para disenar un plan inicial seguro: "
            "goal, biological_sex, age, height_cm, weight_kg, experience_level, days_per_week, session_duration_minutes, equipment. "
            "Bloques de entrevista: 1 datos personales/objetivo; 2 experiencia/rutina/resultados/marcas; 3 disponibilidad/dias/duracion/lugar; "
            "4 equipamiento; 5 preferencias/prioridades; 6 molestias/lesiones; 7 sueno/estres/actividad; 8 nutricion/objetivo temporal; 9 registro/seguimiento. "
            "ready_for_plan solo puede ser true cuando no falte ningun dato imprescindible. Contexto estructurado: "
            f"{json.dumps(safe_context, ensure_ascii=False)}"
        )

    def _parse_model_response(self, data: Any) -> AiProviderResult:
        if not isinstance(data, dict):
            raise AiProviderError("Ollama response is not an object.")
        recommendation = self._text(data.get("recommendation"))
        explanation = self._text(data.get("explanation"))
        risk_notes = self._text(data.get("risk_notes"), required=False)
        confidence = self._text(data.get("confidence"))
        if confidence not in VALID_CONFIDENCE:
            raise AiProviderError("Ollama confidence is invalid.")
        return AiProviderResult(
            recommendation=recommendation,
            explanation=explanation,
            risk_notes=risk_notes,
            confidence=confidence,
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def _parse_training_plan_response(self, data: Any) -> AiTrainingPlanProviderResult:
        if not isinstance(data, dict):
            raise AiProviderError("Ollama response is not an object.")
        explanation = self._text(data.get("explanation"))
        risk_notes = self._text(data.get("risk_notes"), required=False)
        confidence = self._text(data.get("confidence"))
        if confidence not in VALID_CONFIDENCE:
            raise AiProviderError("Ollama confidence is invalid.")
        return AiTrainingPlanProviderResult(
            explanation=explanation,
            risk_notes=risk_notes,
            confidence=confidence,
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def _parse_training_plan_structure_response(self, data: Any) -> AiTrainingPlanStructureProviderResult:
        if not isinstance(data, dict):
            raise AiProviderError("Ollama response is not an object.")
        if data.get("version") == 3:
            explanation = self._text(data.get("explanation") or (data.get("coach_rationale") or {}).get("summary"))
            risk_notes = self._text(data.get("risk_notes"), required=False)
            confidence_value = data.get("confidence") or "medium"
            confidence = self._text(confidence_value)
            if confidence not in VALID_CONFIDENCE:
                raise AiProviderError("Ollama confidence is invalid.")
            return AiTrainingPlanStructureProviderResult(
                plan_payload=data,
                explanation=explanation,
                risk_notes=risk_notes,
                confidence=confidence,
                provider=self.provider,
                model=self.model,
                external_data_sent=self.external_data_sent,
            )
        routines = data.get("routines")
        if not isinstance(routines, list):
            raise AiProviderError("Ollama training plan routines are invalid.")
        progression = self._text(data.get("progression"))
        explanation = self._text(data.get("explanation"))
        risk_notes = self._text(data.get("risk_notes"), required=False)
        confidence = self._text(data.get("confidence"))
        if confidence not in VALID_CONFIDENCE:
            raise AiProviderError("Ollama confidence is invalid.")
        return AiTrainingPlanStructureProviderResult(
            plan_payload={"version": 2, "routines": routines, "progression": progression},
            explanation=explanation,
            risk_notes=risk_notes,
            confidence=confidence,
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def _parse_session_summary_response(self, data: Any) -> AiSessionSummaryProviderResult:
        if not isinstance(data, dict):
            raise AiProviderError("Ollama response is not an object.")
        return AiSessionSummaryProviderResult(
            summary=self._text(data.get("summary")) or "",
            improvements=self._string_list(data.get("improvements")),
            drops=self._string_list(data.get("drops")),
            warnings=self._string_list(data.get("warnings")),
            next_recommendation=self._text(data.get("next_recommendation")) or "",
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def _parse_coach_interview_response(self, data: Any) -> CoachInterviewProviderResult:
        if not isinstance(data, dict):
            raise AiProviderError("Coach interview response is not an object.")
        profile_updates = data.get("profile_updates")
        if not isinstance(profile_updates, dict):
            raise AiProviderError("Coach profile updates are invalid.")
        return CoachInterviewProviderResult(
            assistant_message=self._long_text(data.get("assistant_message")),
            profile_updates=profile_updates,
            known_facts=self._string_list(data.get("known_facts")),
            missing_critical=self._string_list(data.get("missing_critical")),
            missing_useful=self._string_list(data.get("missing_useful")),
            estimated_fields=self._string_list(data.get("estimated_fields")),
            misunderstanding_corrections=self._string_list(data.get("misunderstanding_corrections")),
            safety_flags=self._string_list(data.get("safety_flags")),
            ready_for_plan=bool(data.get("ready_for_plan")),
            next_questions=self._string_list(data.get("next_questions")),
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def _text(self, value: Any, *, required: bool = True) -> str | None:
        if value is None and not required:
            return None
        if not isinstance(value, str):
            raise AiProviderError("Ollama text field is invalid.")
        cleaned = value.strip()
        if not cleaned and required:
            raise AiProviderError("Ollama text field is empty.")
        return cleaned[:MAX_TEXT_LENGTH]

    def _long_text(self, value: Any, *, required: bool = True) -> str | None:
        if value is None and not required:
            return None
        if not isinstance(value, str):
            raise AiProviderError("Ollama text field is invalid.")
        cleaned = value.strip()
        if not cleaned and required:
            raise AiProviderError("Ollama text field is empty.")
        return cleaned[:4_000]

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise AiProviderError("Ollama list field is invalid.")
        cleaned: list[str] = []
        for item in value[:20]:
            if not isinstance(item, str):
                raise AiProviderError("Ollama list item is invalid.")
            text = item.strip()
            if text:
                cleaned.append(text[:MAX_TEXT_LENGTH])
        return cleaned


class GroqAiProvider(OllamaAiProvider):
    provider = "groq"
    external_data_sent = True

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ai_groq_base_url.rstrip("/")
        self.model = settings.ai_groq_model
        self.api_key = settings.ai_groq_api_key or ""
        self.timeout_seconds = settings.ai_timeout_seconds

    def build_explanation(self, context: AiProviderContext) -> AiProviderResult:
        return self._parse_model_response(self._chat_json(self._prompt(context)))

    def build_training_plan_text(self, context: AiTrainingPlanProviderContext) -> AiTrainingPlanProviderResult:
        return self._parse_training_plan_response(self._chat_json(self._training_plan_prompt(context)))

    def build_training_plan_structure(self, context: AiTrainingPlanProviderContext) -> AiTrainingPlanStructureProviderResult:
        return self._parse_training_plan_structure_response(self._chat_json(self._training_plan_structure_prompt(context)))

    def build_session_summary_text(self, context: AiSessionSummaryProviderContext) -> AiSessionSummaryProviderResult:
        return self._parse_session_summary_response(self._chat_json(self._session_summary_prompt(context)))

    def build_coach_interview_response(self, context: CoachInterviewProviderContext) -> CoachInterviewProviderResult:
        return self._parse_coach_interview_response(self._chat_json(self._coach_interview_prompt(context)))

    def _chat_json(self, prompt: str) -> Any:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Devuelve solo JSON valido, sin markdown."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except (OSError, URLError) as error:
            raise AiProviderError("Groq request failed.") from error

        try:
            parsed = json.loads(raw)
            content = parsed["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise AiProviderError("Groq returned invalid JSON.") from error


def build_ai_provider(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.ai_provider == "groq":
        return GroqAiProvider(settings)
    if settings.ai_provider == "ollama":
        return OllamaAiProvider(settings)
    return InternalAiProvider()


def enrich_with_provider(context: AiProviderContext, settings: Settings | None = None) -> AiProviderResult:
    internal = InternalAiProvider()
    provider = build_ai_provider(settings)
    try:
        return provider.build_explanation(context)
    except AiProviderError:
        fallback = internal.build_explanation(context)
        return AiProviderResult(
            recommendation=fallback.recommendation,
            explanation=fallback.explanation,
            risk_notes=fallback.risk_notes,
            confidence=fallback.confidence,
            provider=getattr(provider, "provider", "unknown"),
            model=getattr(provider, "model", None),
            external_data_sent=getattr(provider, "external_data_sent", False),
            fallback_used=True,
        )


def enrich_training_plan_with_provider(
    context: AiTrainingPlanProviderContext, settings: Settings | None = None
) -> AiTrainingPlanProviderResult:
    internal = InternalAiProvider()
    provider = build_ai_provider(settings)
    try:
        return provider.build_training_plan_text(context)
    except AiProviderError:
        fallback = internal.build_training_plan_text(context)
        return AiTrainingPlanProviderResult(
            explanation=fallback.explanation,
            risk_notes=fallback.risk_notes,
            confidence=fallback.confidence,
            provider=getattr(provider, "provider", "unknown"),
            model=getattr(provider, "model", None),
            external_data_sent=getattr(provider, "external_data_sent", False),
            fallback_used=True,
        )


def enrich_session_summary_with_provider(
    context: AiSessionSummaryProviderContext, settings: Settings | None = None
) -> AiSessionSummaryProviderResult:
    internal = InternalAiProvider()
    provider = build_ai_provider(settings)
    try:
        return provider.build_session_summary_text(context)
    except AiProviderError:
        fallback = internal.build_session_summary_text(context)
        return AiSessionSummaryProviderResult(
            summary=fallback.summary,
            improvements=fallback.improvements,
            drops=fallback.drops,
            warnings=fallback.warnings,
            next_recommendation=fallback.next_recommendation,
            provider=getattr(provider, "provider", "unknown"),
            model=getattr(provider, "model", None),
            external_data_sent=getattr(provider, "external_data_sent", False),
            fallback_used=True,
        )
