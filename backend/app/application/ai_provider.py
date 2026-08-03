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
class AiCoachQuestionProviderContext:
    question_type: str
    input_summary: dict[str, Any]
    answer: str
    key_points: list[str]
    suggested_actions: list[str]


@dataclass(frozen=True)
class AiCoachQuestionProviderResult:
    answer: str
    key_points: list[str]
    suggested_actions: list[str]
    provider: str
    model: str | None
    external_data_sent: bool
    fallback_used: bool = False


@dataclass(frozen=True)
class AiCoachIntakeProviderContext:
    intake_summary: dict[str, Any]
    recent_messages: list[dict[str, Any]]
    user_message: str | None
    missing_required_fields: list[str]
    useful_missing_fields: list[str]
    sensitive_data_acknowledged: bool


@dataclass(frozen=True)
class AiCoachIntakeProviderResult:
    assistant_message: str
    extracted_fields: dict[str, Any]
    missing_required_fields: list[str]
    useful_missing_fields: list[str]
    estimated_fields: list[str]
    ready_for_plan: bool
    safety_warning: str | None
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

    def build_coach_question_text(self, context: AiCoachQuestionProviderContext) -> AiCoachQuestionProviderResult:
        return AiCoachQuestionProviderResult(
            answer=context.answer,
            key_points=context.key_points,
            suggested_actions=context.suggested_actions,
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def build_coach_intake_response(self, context: AiCoachIntakeProviderContext) -> AiCoachIntakeProviderResult:
        missing = context.missing_required_fields
        useful = context.useful_missing_fields
        if missing:
            next_field = missing[0]
            question = {
                "goal": "Para ajustar el plan, dime tu objetivo principal: fuerza, hipertrofia, perdida de grasa, salud general o resistencia.",
                "level": "Cual es tu nivel actual: principiante, intermedio o avanzado?",
                "days_per_week": "Cuantos dias por semana puedes entrenar de forma realista?",
                "session_duration_minutes": "Cuantos minutos tienes por sesion?",
            }.get(next_field, "Dame un poco mas de contexto para completar tu plan.")
        elif useful:
            question = "Ya tengo lo imprescindible. Si quieres afinarlo, dime equipamiento disponible, prioridades musculares o limitaciones fisicas. Si no, puedo generar el plan."
        else:
            question = "Tengo suficiente informacion para crear un borrador de plan. Revisalo antes de aceptarlo."
        return AiCoachIntakeProviderResult(
            assistant_message=question,
            extracted_fields={},
            missing_required_fields=missing,
            useful_missing_fields=useful,
            estimated_fields=[],
            ready_for_plan=not missing,
            safety_warning=self._intake_safety_warning(context.sensitive_data_acknowledged),
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

    def _intake_safety_warning(self, sensitive_data_acknowledged: bool) -> str | None:
        if sensitive_data_acknowledged:
            return "Las limitaciones indicadas sirven solo para adaptar el plan; no sustituyen consejo medico o profesional."
        return None


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

    def build_coach_question_text(self, context: AiCoachQuestionProviderContext) -> AiCoachQuestionProviderResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._coach_question_prompt(context),
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

        return self._parse_coach_question_response(model_response)

    def build_coach_intake_response(self, context: AiCoachIntakeProviderContext) -> AiCoachIntakeProviderResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "prompt": self._coach_intake_prompt(context),
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

        return self._parse_coach_intake_response(model_response)

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
            "weekly_schedule, volume_by_muscle, progression_model, routines, validation_report, acceptance_effects, explanation, risk_notes, confidence. "
            f"version debe ser 3. generated_by.provider debe ser {self.provider}. confidence debe ser low, medium o high. "
            "Primero disena la arquitectura del programa: split, volumen semanal por musculo, roles por dia y progresion. Luego elige ejercicios. "
            "No uses ejercicios que el usuario pidio evitar en priorities con formato 'evitar ...'. "
            "routines debe tener exactamente days_per_week elementos. Cada routine debe tener: day, name, focus, description, target_duration_minutes, session_role, exercises. "
            "Cada exercise debe tener: exercise_id null, exercise_name, description, technique_notes, difficulty, equipment, slot, role, movement_pattern, "
            "primary_muscle, secondary_muscles, target_sets, target_reps_min, target_reps_max, target_rpe, target_rir, rest_seconds, reason, progression_hint. "
            "Rangos seguros: target_sets 1-8, reps 1-30, target_rpe 6-9, target_rir 0-4, rest_seconds 45-300. "
            "Usa compuestos antes que accesorios, reparte volumen por semana, justifica cada ejercicio y declara que ejercicios nuevos se crearan solo al aceptar. "
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

    def _coach_question_prompt(self, context: AiCoachQuestionProviderContext) -> str:
        safe_context = {
            "question_type": context.question_type,
            "input_summary": context.input_summary,
            "base_answer": context.answer,
            "base_key_points": context.key_points,
            "base_suggested_actions": context.suggested_actions,
        }
        return (
            "Eres un entrenador de fuerza. Devuelve solo JSON valido con keys: "
            "answer, key_points, suggested_actions. key_points y suggested_actions deben ser arrays de strings. "
            "Responde solo la pregunta guiada, no apliques cambios ni digas que modificaste rutinas o sesiones. "
            "No menciones datos personales, notas privadas, diagnosticos ni datos medicos. Contexto estructurado: "
            f"{json.dumps(safe_context, ensure_ascii=False)}"
        )

    def _coach_intake_prompt(self, context: AiCoachIntakeProviderContext) -> str:
        safe_context = {
            "intake_summary": context.intake_summary,
            "recent_messages": context.recent_messages[-4:],
            "latest_user_message": context.user_message,
            "missing_required_fields": context.missing_required_fields,
            "useful_missing_fields": context.useful_missing_fields,
            "sensitive_data_acknowledged": context.sensitive_data_acknowledged,
        }
        return (
            "Eres el entrenador personal de Zenith. Haz una entrevista inicial por bloques manejables. "
            "No generes un plan todavia: solo recopila datos, resume campos y pregunta lo siguiente. "
            "No inventes fuentes, diagnosticos, datos personales ni promesas absolutas. "
            "Si faltan campos obligatorios, pregunta solo por el mas importante. "
            "Si hay datos suficientes, marca ready_for_plan=true e invita a generar un borrador revisable. "
            "Devuelve solo JSON valido con keys: assistant_message, extracted_fields, missing_required_fields, "
            "useful_missing_fields, estimated_fields, ready_for_plan, safety_warning. "
            "extracted_fields solo puede incluir: goal, level, days_per_week, session_duration_minutes, "
            "available_equipment, priorities, physical_limitations. goal debe ser strength, hypertrophy, fat_loss, "
            "general_health o endurance. level debe ser beginner, intermediate o advanced. "
            "No incluyas physical_limitations si sensitive_data_acknowledged=false. Contexto estructurado: "
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

    def _parse_coach_question_response(self, data: Any) -> AiCoachQuestionProviderResult:
        if not isinstance(data, dict):
            raise AiProviderError("Ollama response is not an object.")
        return AiCoachQuestionProviderResult(
            answer=self._text(data.get("answer")) or "",
            key_points=self._string_list(data.get("key_points")),
            suggested_actions=self._string_list(data.get("suggested_actions")),
            provider=self.provider,
            model=self.model,
            external_data_sent=self.external_data_sent,
        )

    def _parse_coach_intake_response(self, data: Any) -> AiCoachIntakeProviderResult:
        if not isinstance(data, dict):
            raise AiProviderError("Ollama response is not an object.")
        extracted_fields = data.get("extracted_fields")
        if not isinstance(extracted_fields, dict):
            raise AiProviderError("Ollama extracted fields are invalid.")
        return AiCoachIntakeProviderResult(
            assistant_message=self._text(data.get("assistant_message")) or "",
            extracted_fields=extracted_fields,
            missing_required_fields=self._string_list(data.get("missing_required_fields")),
            useful_missing_fields=self._string_list(data.get("useful_missing_fields")),
            estimated_fields=self._string_list(data.get("estimated_fields")),
            ready_for_plan=bool(data.get("ready_for_plan")),
            safety_warning=self._text(data.get("safety_warning"), required=False),
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

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise AiProviderError("Ollama list field is invalid.")
        cleaned: list[str] = []
        for item in value[:8]:
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

    def build_coach_question_text(self, context: AiCoachQuestionProviderContext) -> AiCoachQuestionProviderResult:
        return self._parse_coach_question_response(self._chat_json(self._coach_question_prompt(context)))

    def build_coach_intake_response(self, context: AiCoachIntakeProviderContext) -> AiCoachIntakeProviderResult:
        return self._parse_coach_intake_response(self._chat_json(self._coach_intake_prompt(context)))

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


def enrich_coach_question_with_provider(
    context: AiCoachQuestionProviderContext, settings: Settings | None = None
) -> AiCoachQuestionProviderResult:
    internal = InternalAiProvider()
    provider = build_ai_provider(settings)
    try:
        return provider.build_coach_question_text(context)
    except AiProviderError:
        fallback = internal.build_coach_question_text(context)
        return AiCoachQuestionProviderResult(
            answer=fallback.answer,
            key_points=fallback.key_points,
            suggested_actions=fallback.suggested_actions,
            provider=getattr(provider, "provider", "unknown"),
            model=getattr(provider, "model", None),
            external_data_sent=getattr(provider, "external_data_sent", False),
            fallback_used=True,
        )


def enrich_coach_intake_with_provider(
    context: AiCoachIntakeProviderContext, settings: Settings | None = None
) -> AiCoachIntakeProviderResult:
    internal = InternalAiProvider()
    provider = build_ai_provider(settings)
    try:
        return provider.build_coach_intake_response(context)
    except AiProviderError:
        fallback = internal.build_coach_intake_response(context)
        return AiCoachIntakeProviderResult(
            assistant_message=fallback.assistant_message,
            extracted_fields=fallback.extracted_fields,
            missing_required_fields=fallback.missing_required_fields,
            useful_missing_fields=fallback.useful_missing_fields,
            estimated_fields=fallback.estimated_fields,
            ready_for_plan=fallback.ready_for_plan,
            safety_warning=fallback.safety_warning,
            provider=getattr(provider, "provider", "unknown"),
            model=getattr(provider, "model", None),
            external_data_sent=getattr(provider, "external_data_sent", False),
            fallback_used=True,
        )
