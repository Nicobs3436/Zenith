import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.application.ai_provider import AiCoachIntakeProviderContext, enrich_coach_intake_with_provider
from app.application.ai_training_plan_service import AiTrainingPlanCannotGenerateError, ai_training_plan_service
from app.domain.ai import AiCoachIntakeMessageRequest, AiCoachIntakeRead, AiTrainingPlanGenerateRequest
from app.infrastructure.db.models.ai import AiCoachIntake, AiTrainingPlan
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.coach_intakes import AiCoachIntakeRepository

REQUIRED_FIELDS = ["goal", "level", "days_per_week", "session_duration_minutes"]
USEFUL_FIELDS = ["available_equipment", "priorities", "physical_limitations"]
SENSITIVE_MARKERS = ["dolor", "lesion", "lesión", "molestia", "rodilla", "hombro", "espalda", "limitacion", "limitación"]


class AiCoachIntakeCannotGenerateError(Exception):
    pass


class AiCoachIntakeService:
    def get_intake(self, db: Session, user: User) -> AiCoachIntakeRead:
        intake = AiCoachIntakeRepository(db).get_or_create(user.id)
        missing = self._missing_required_fields(intake.intake_summary)
        useful = self._useful_missing_fields(intake.intake_summary)
        db.commit()
        return self._read(
            intake,
            assistant_message=self._base_assistant_message(missing, useful),
            missing_required_fields=missing,
            useful_missing_fields=useful,
        )

    def add_message(self, db: Session, user: User, data: AiCoachIntakeMessageRequest) -> AiCoachIntakeRead:
        repository = AiCoachIntakeRepository(db)
        intake = repository.get_or_create(user.id)
        sensitive_acknowledged = intake.sensitive_data_acknowledged or data.sensitive_data_acknowledged
        has_sensitive_text = self._has_sensitive_text(data.message)

        local_fields = self._extract_fields(data.message, sensitive_data_acknowledged=sensitive_acknowledged)
        summary = self._merge_summary(intake.intake_summary, local_fields, sensitive_data_acknowledged=sensitive_acknowledged)
        missing = self._missing_required_fields(summary)
        useful = self._useful_missing_fields(summary)
        safe_message = data.message if sensitive_acknowledged or not has_sensitive_text else None

        provider_result = enrich_coach_intake_with_provider(
            AiCoachIntakeProviderContext(
                intake_summary=summary,
                recent_messages=intake.recent_messages,
                user_message=safe_message,
                missing_required_fields=missing,
                useful_missing_fields=useful,
                sensitive_data_acknowledged=sensitive_acknowledged,
            )
        )
        provider_fields = self._validated_fields(
            provider_result.extracted_fields,
            sensitive_data_acknowledged=sensitive_acknowledged,
        )
        summary = self._merge_summary(summary, provider_fields, sensitive_data_acknowledged=sensitive_acknowledged)
        missing = self._missing_required_fields(summary)
        useful = self._useful_missing_fields(summary)
        ready_for_plan = not missing
        safety_warning = provider_result.safety_warning
        if has_sensitive_text and not sensitive_acknowledged:
            safety_warning = "Has mencionado posibles limitaciones fisicas. Confirma el aviso medico para usarlas al adaptar el plan."

        intake.intake_summary = summary
        intake.missing_required_fields = missing
        intake.ready_for_plan = ready_for_plan
        intake.status = "ready" if ready_for_plan else "collecting"
        intake.sensitive_data_acknowledged = sensitive_acknowledged
        intake.recent_messages = self._recent_messages(
            intake.recent_messages,
            user_message=data.message,
            assistant_message=provider_result.assistant_message,
            redact_user_message=has_sensitive_text and not sensitive_acknowledged,
        )
        db.commit()
        refreshed = repository.get_by_user(user.id) or intake
        return self._read(
            refreshed,
            assistant_message=provider_result.assistant_message,
            missing_required_fields=missing,
            useful_missing_fields=useful,
            safety_warning=safety_warning,
            provider=provider_result.provider,
            model=provider_result.model,
            fallback_used=provider_result.fallback_used,
        )

    def reset_intake(self, db: Session, user: User) -> AiCoachIntakeRead:
        intake = AiCoachIntakeRepository(db).reset(user.id)
        missing = self._missing_required_fields(intake.intake_summary)
        useful = self._useful_missing_fields(intake.intake_summary)
        intake.missing_required_fields = missing
        db.commit()
        return self._read(
            intake,
            assistant_message=self._base_assistant_message(missing, useful),
            missing_required_fields=missing,
            useful_missing_fields=useful,
        )

    def generate_plan(self, db: Session, user: User) -> AiTrainingPlan:
        repository = AiCoachIntakeRepository(db)
        intake = repository.get_by_user(user.id)
        if intake is None:
            raise AiCoachIntakeCannotGenerateError("Coach intake not found.")
        missing = self._missing_required_fields(intake.intake_summary)
        if missing:
            raise AiCoachIntakeCannotGenerateError("Coach intake is missing required fields.")
        request = self._training_plan_request(intake)
        try:
            plan = ai_training_plan_service.generate_plan(db, user, request)
        except AiTrainingPlanCannotGenerateError as error:
            raise AiCoachIntakeCannotGenerateError(str(error)) from error

        intake = repository.get_by_user(user.id) or intake
        intake.status = "plan_generated"
        intake.ready_for_plan = True
        db.commit()
        return plan

    def _read(
        self,
        intake: AiCoachIntake,
        *,
        assistant_message: str | None,
        missing_required_fields: list[str],
        useful_missing_fields: list[str],
        safety_warning: str | None = None,
        provider: str = "internal",
        model: str | None = None,
        fallback_used: bool = False,
    ) -> AiCoachIntakeRead:
        return AiCoachIntakeRead(
            id=intake.id,
            user_id=intake.user_id,
            status=intake.status,
            intake_summary=intake.intake_summary,
            recent_messages=intake.recent_messages,
            missing_required_fields=missing_required_fields,
            useful_missing_fields=useful_missing_fields,
            ready_for_plan=not missing_required_fields,
            sensitive_data_acknowledged=intake.sensitive_data_acknowledged,
            assistant_message=assistant_message,
            safety_warning=safety_warning,
            provider=provider,
            model=model,
            fallback_used=fallback_used,
            updated_at=intake.updated_at,
        )

    def _training_plan_request(self, intake: AiCoachIntake) -> AiTrainingPlanGenerateRequest:
        summary = intake.intake_summary
        return AiTrainingPlanGenerateRequest(
            goal=summary["goal"],
            level=summary["level"],
            days_per_week=int(summary["days_per_week"]),
            session_duration_minutes=int(summary["session_duration_minutes"]),
            available_equipment=self._string_values(summary.get("available_equipment")),
            physical_limitations=summary.get("physical_limitations") if intake.sensitive_data_acknowledged else None,
            sensitive_data_acknowledged=intake.sensitive_data_acknowledged,
            priorities=self._string_values(summary.get("priorities")),
        )

    def _extract_fields(self, message: str, *, sensitive_data_acknowledged: bool) -> dict[str, Any]:
        normalized = self._normalize(message)
        fields: dict[str, Any] = {}
        if any(marker in normalized for marker in ["hipertrof", "musculo", "masa muscular", "volumen"]):
            fields["goal"] = "hypertrophy"
        elif any(marker in normalized for marker in ["fuerza", "strength"]):
            fields["goal"] = "strength"
        elif any(marker in normalized for marker in ["perder grasa", "grasa", "adelgazar", "definir"]):
            fields["goal"] = "fat_loss"
        elif any(marker in normalized for marker in ["salud", "general"]):
            fields["goal"] = "general_health"
        elif any(marker in normalized for marker in ["resistencia", "endurance"]):
            fields["goal"] = "endurance"

        if any(marker in normalized for marker in ["principiante", "novato", "beginner"]):
            fields["level"] = "beginner"
        elif any(marker in normalized for marker in ["intermedio", "intermediate"]):
            fields["level"] = "intermediate"
        elif any(marker in normalized for marker in ["avanzado", "advanced"]):
            fields["level"] = "advanced"

        day_match = re.search(r"\b([1-7])\s*(dias|días|days)\b", normalized)
        if day_match:
            fields["days_per_week"] = int(day_match.group(1))
        minute_match = re.search(r"\b(2[0-9]|[3-9][0-9]|1[0-7][0-9]|180)\s*(min|mins|minutos|minutes)\b", normalized)
        if minute_match:
            fields["session_duration_minutes"] = int(minute_match.group(1))

        equipment = [item for item in ["mancuernas", "barra", "banco", "polea", "maquina", "bandas", "peso corporal"] if item in normalized]
        if equipment:
            fields["available_equipment"] = equipment
        priorities = [item for item in ["pecho", "espalda", "pierna", "hombro", "gluteo", "brazos", "core"] if item in normalized]
        if priorities:
            fields["priorities"] = priorities
        if sensitive_data_acknowledged and self._has_sensitive_text(message):
            fields["physical_limitations"] = message[:500]
        return fields

    def _validated_fields(self, fields: dict[str, Any], *, sensitive_data_acknowledged: bool) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        goal = fields.get("goal")
        if goal in {"strength", "hypertrophy", "fat_loss", "general_health", "endurance"}:
            cleaned["goal"] = goal
        level = fields.get("level")
        if level in {"beginner", "intermediate", "advanced"}:
            cleaned["level"] = level
        for field in ["days_per_week", "session_duration_minutes"]:
            try:
                value = int(fields[field])
            except (KeyError, TypeError, ValueError):
                continue
            if field == "days_per_week" and 1 <= value <= 7:
                cleaned[field] = value
            if field == "session_duration_minutes" and 20 <= value <= 180:
                cleaned[field] = value
        for field in ["available_equipment", "priorities"]:
            values = self._string_values(fields.get(field))[:10]
            if values:
                cleaned[field] = values
        limitation = fields.get("physical_limitations")
        if sensitive_data_acknowledged and isinstance(limitation, str) and limitation.strip():
            cleaned["physical_limitations"] = limitation.strip()[:500]
        return cleaned

    def _merge_summary(self, current: dict[str, Any], new_fields: dict[str, Any], *, sensitive_data_acknowledged: bool) -> dict[str, Any]:
        summary = dict(current or {})
        for key, value in self._validated_fields(new_fields, sensitive_data_acknowledged=sensitive_data_acknowledged).items():
            if key in {"available_equipment", "priorities"}:
                summary[key] = sorted({*self._string_values(summary.get(key)), *self._string_values(value)})
            else:
                summary[key] = value
        if not sensitive_data_acknowledged:
            summary.pop("physical_limitations", None)
        return summary

    def _missing_required_fields(self, summary: dict[str, Any]) -> list[str]:
        return [field for field in REQUIRED_FIELDS if summary.get(field) in (None, "", [])]

    def _useful_missing_fields(self, summary: dict[str, Any]) -> list[str]:
        return [field for field in USEFUL_FIELDS if summary.get(field) in (None, "", [])]

    def _recent_messages(
        self,
        current: list[dict[str, Any]],
        *,
        user_message: str,
        assistant_message: str,
        redact_user_message: bool,
    ) -> list[dict[str, Any]]:
        stored_user_message = "[dato sensible no guardado: confirma el aviso medico para usar limitaciones]" if redact_user_message else user_message
        messages = [*list(current or []), {"role": "user", "content": stored_user_message[:500]}, {"role": "assistant", "content": assistant_message[:500]}]
        return messages[-6:]

    def _base_assistant_message(self, missing: list[str], useful: list[str]) -> str:
        if missing:
            return "Cuéntame tu objetivo, nivel, dias disponibles y minutos por sesion para crear un plan revisable."
        if useful:
            return "Tengo lo imprescindible. Puedes añadir equipamiento, prioridades o limitaciones antes de generar el plan."
        return "Tengo suficiente informacion para generar un borrador de plan."

    def _string_values(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip()[:80])
        return cleaned

    def _has_sensitive_text(self, value: str) -> bool:
        normalized = self._normalize(value)
        return any(marker in normalized for marker in SENSITIVE_MARKERS)

    def _normalize(self, value: str) -> str:
        return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


ai_coach_intake_service = AiCoachIntakeService()
