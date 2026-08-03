import re
import unicodedata
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.ai_training_plan_service import (
    AiTrainingPlanCannotGenerateError,
    AiTrainingPlanNotDraftError,
    AiTrainingPlanNotFoundError,
    ai_training_plan_service,
)
from app.domain.ai import (
    AiTrainingPlanGenerateRequest,
    AiTrainingPlanModifyRequest,
    CoachMessageRequest,
    CoachStateRead,
)
from app.infrastructure.db.models.ai import AiTrainingPlan, CoachConversation, CoachProfile
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.coach_v2 import CoachV2Repository
from app.infrastructure.db.repositories.training_plans import AiTrainingPlanRepository

REQUIRED_PROFILE_FIELDS = [
    "personal_data_acknowledged",
    "goal",
    "biological_sex",
    "age",
    "height_cm",
    "weight_kg",
    "experience_level",
    "days_per_week",
    "session_duration_minutes",
    "equipment",
]

EQUIPMENT_FULL_GYM = ["mancuernas", "barra", "banco", "polea", "maquina", "peso corporal"]
GOALS = {"strength", "hypertrophy", "fat_loss", "general_health", "endurance"}
LEVELS = {"beginner", "intermediate", "advanced"}
COACH_SOURCE = "coach_clean"


class CoachCannotGenerateError(Exception):
    pass


class CoachPlanNotFoundError(Exception):
    pass


class CoachPlanNotDraftError(Exception):
    pass


class CoachService:
    def get_state(self, db: Session, user: User) -> CoachStateRead:
        repository = CoachV2Repository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        conversation.phase = self._phase(db, user.id, profile)
        db.commit()
        return self._state(db, repository, user.id, profile, conversation, self._assistant_prompt(profile))

    def add_message(self, db: Session, user: User, data: CoachMessageRequest) -> CoachStateRead:
        repository = CoachV2Repository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)

        if data.personal_data_acknowledged:
            profile.personal_data_acknowledged = True
        if data.sensitive_data_acknowledged:
            profile.sensitive_data_acknowledged = True

        extracted = self._extract_fields(data.message, profile)
        changed = self._apply_fields(profile, extracted)
        assistant_message = self._assistant_response(profile, changed)
        conversation.recent_messages = self._recent_messages(conversation.recent_messages, data.message, assistant_message)
        conversation.conversation_summary = self._summary(profile)
        conversation.last_question = self._missing_required_fields(profile)[0] if self._missing_required_fields(profile) else None
        profile.memory_summary = self._summary(profile)
        conversation.phase = self._phase(db, user.id, profile)
        if changed:
            repository.add_memory(
                user_id=user.id,
                event_type="profile_updated",
                summary=f"Coach actualizo perfil: {', '.join(changed)}.",
                payload={"fields": changed},
            )
        db.commit()
        return self._state(db, repository, user.id, profile, conversation, assistant_message)

    def generate_plan(self, db: Session, user: User) -> AiTrainingPlan:
        repository = CoachV2Repository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        missing = self._missing_required_fields(profile)
        if missing:
            raise CoachCannotGenerateError("Coach profile is missing required fields.")

        request = AiTrainingPlanGenerateRequest(
            goal=profile.goal,
            level=profile.experience_level,
            days_per_week=profile.days_per_week,
            session_duration_minutes=profile.session_duration_minutes,
            available_equipment=profile.equipment,
            physical_limitations=profile.physical_limitations if profile.sensitive_data_acknowledged else None,
            sensitive_data_acknowledged=profile.sensitive_data_acknowledged,
            priorities=self._plan_priorities(profile),
        )
        try:
            plan = ai_training_plan_service.generate_plan(
                db,
                user,
                request,
                require_ai_provider=True,
                coach_brief=self._coach_brief(profile),
            )
        except AiTrainingPlanCannotGenerateError as error:
            raise CoachCannotGenerateError(str(error)) from error

        self._mark_coach_plan(plan)
        conversation.phase = "plan_draft"
        repository.add_memory(
            user_id=user.id,
            event_type="plan_generated",
            summary="Coach genero un plan borrador revisable.",
            payload={"plan_id": str(plan.id), "source": COACH_SOURCE},
        )
        db.commit()
        return plan

    def accept_plan(self, db: Session, plan_id: UUID, user: User) -> AiTrainingPlan:
        self._get_coach_plan(db, plan_id, user.id)
        try:
            plan = ai_training_plan_service.accept_plan(db, plan_id, user)
        except AiTrainingPlanNotFoundError as error:
            raise CoachPlanNotFoundError from error
        except AiTrainingPlanNotDraftError as error:
            raise CoachPlanNotDraftError from error
        except AiTrainingPlanCannotGenerateError as error:
            raise CoachCannotGenerateError(str(error)) from error

        repository = CoachV2Repository(db)
        conversation = repository.get_or_create_conversation(user.id)
        conversation.phase = "training_active"
        repository.add_memory(
            user_id=user.id,
            event_type="plan_accepted",
            summary="Coach aplico el plan aceptado y creo rutinas reales.",
            payload={"plan_id": str(plan.id)},
        )
        db.commit()
        return plan

    def reject_plan(self, db: Session, plan_id: UUID, user: User) -> AiTrainingPlan:
        self._get_coach_plan(db, plan_id, user.id)
        try:
            plan = ai_training_plan_service.reject_plan(db, plan_id, user)
        except AiTrainingPlanNotFoundError as error:
            raise CoachPlanNotFoundError from error
        except AiTrainingPlanNotDraftError as error:
            raise CoachPlanNotDraftError from error
        CoachV2Repository(db).get_or_create_conversation(user.id).phase = self._phase(db, user.id, CoachV2Repository(db).get_or_create_profile(user.id))
        db.commit()
        return plan

    def modify_plan(self, db: Session, plan_id: UUID, user: User, data: AiTrainingPlanModifyRequest) -> AiTrainingPlan:
        self._get_coach_plan(db, plan_id, user.id)
        try:
            plan = ai_training_plan_service.modify_plan(db, plan_id, user, data)
        except AiTrainingPlanNotFoundError as error:
            raise CoachPlanNotFoundError from error
        except AiTrainingPlanNotDraftError as error:
            raise CoachPlanNotDraftError from error
        except AiTrainingPlanCannotGenerateError as error:
            raise CoachCannotGenerateError(str(error)) from error
        self._mark_coach_plan(plan)
        db.commit()
        return plan

    def reset(self, db: Session, user: User) -> CoachStateRead:
        repository = CoachV2Repository(db)
        profile, conversation = repository.reset(user.id)
        conversation.phase = "onboarding"
        db.commit()
        return self._state(db, repository, user.id, profile, conversation, self._assistant_prompt(profile))

    def _state(
        self,
        db: Session,
        repository: CoachV2Repository,
        user_id: UUID,
        profile: CoachProfile,
        conversation: CoachConversation,
        assistant_message: str,
    ) -> CoachStateRead:
        coach_plans = self._coach_plans(db, user_id)
        draft_plans = [plan for plan in coach_plans if plan.status == "draft"]
        accepted_plan = next((plan for plan in coach_plans if plan.status == "accepted"), None)
        missing = self._missing_required_fields(profile)
        phase = self._phase_from_plans(profile, draft_plans, accepted_plan)
        conversation.phase = phase
        db.flush()
        return CoachStateRead(
            profile=profile,
            phase=phase,
            recent_messages=conversation.recent_messages or [],
            assistant_message=assistant_message,
            missing_required_fields=missing,
            ready_for_plan=not missing,
            draft_plans=draft_plans,
            accepted_plan=accepted_plan,
            privacy_notice="Uso solo los datos necesarios para entrenar: no envio email, usuario, tokens, credenciales ni notas privadas.",
            safety_notice="No sustituyo consejo medico. Si mencionas dolor, lesiones o limitaciones, confirma el aviso medico antes de guardarlas.",
            next_action=self._next_action(missing, draft_plans, accepted_plan),
        )

    def _phase(self, db: Session, user_id: UUID, profile: CoachProfile) -> str:
        plans = self._coach_plans(db, user_id)
        return self._phase_from_plans(
            profile,
            [plan for plan in plans if plan.status == "draft"],
            next((plan for plan in plans if plan.status == "accepted"), None),
        )

    def _phase_from_plans(self, profile: CoachProfile, draft_plans: list[AiTrainingPlan], accepted_plan: AiTrainingPlan | None) -> str:
        if accepted_plan is not None:
            return "training_active"
        if draft_plans:
            return "plan_draft"
        if self._missing_required_fields(profile):
            return "onboarding"
        return "ready_for_plan"

    def _coach_plans(self, db: Session, user_id: UUID) -> list[AiTrainingPlan]:
        return [plan for plan in AiTrainingPlanRepository(db).list_by_user(user_id) if self._is_coach_plan(plan)]

    def _get_coach_plan(self, db: Session, plan_id: UUID, user_id: UUID) -> AiTrainingPlan:
        plan = AiTrainingPlanRepository(db).get_by_user(plan_id, user_id)
        if plan is None or not self._is_coach_plan(plan):
            raise CoachPlanNotFoundError
        return plan

    def _is_coach_plan(self, plan: AiTrainingPlan) -> bool:
        return plan.input_summary.get("source") == COACH_SOURCE or plan.plan_payload.get("coach_version") == 1

    def _mark_coach_plan(self, plan: AiTrainingPlan) -> None:
        plan.input_summary = {**dict(plan.input_summary or {}), "source": COACH_SOURCE}
        plan.plan_payload = {**dict(plan.plan_payload or {}), "coach_version": 1}

    def _missing_required_fields(self, profile: CoachProfile) -> list[str]:
        missing: list[str] = []
        for field in REQUIRED_PROFILE_FIELDS:
            value = getattr(profile, field)
            if isinstance(value, list):
                if not value:
                    missing.append(field)
            elif not value:
                missing.append(field)
        return missing

    def _extract_fields(self, message: str, profile: CoachProfile) -> dict[str, Any]:
        text = self._normalize(message)
        fields: dict[str, Any] = {}

        if any(marker in text for marker in ["acepto", "confirmo", "entiendo", "de acuerdo", "ok"]):
            if "datos" in text or "personal" in text or "aviso" in text:
                fields["personal_data_acknowledged"] = True

        if any(marker in text for marker in ["fuerza", "strength"]):
            fields["goal"] = "strength"
        elif any(marker in text for marker in ["hipertrof", "musculo", "masa muscular", "volumen"]):
            fields["goal"] = "hypertrophy"
        elif any(marker in text for marker in ["perder grasa", "perdida de grasa", "adelgazar", "definir", "grasa"]):
            fields["goal"] = "fat_loss"
        elif any(marker in text for marker in ["salud", "bienestar"]):
            fields["goal"] = "general_health"
        elif any(marker in text for marker in ["resistencia", "cardio", "endurance"]):
            fields["goal"] = "endurance"

        if any(marker in text for marker in ["masculino", "hombre", "male"]):
            fields["biological_sex"] = "male"
        if any(marker in text for marker in ["femenino", "mujer", "female"]):
            fields["biological_sex"] = "female"

        if any(marker in text for marker in ["principiante", "novato", "beginner"]):
            fields["experience_level"] = "beginner"
        elif any(marker in text for marker in ["intermedio", "intermediate"]):
            fields["experience_level"] = "intermediate"
        elif any(marker in text for marker in ["avanzado", "advanced"]):
            fields["experience_level"] = "advanced"

        self._extract_numbers(text, fields)
        self._extract_lists(text, fields)

        if any(marker in text for marker in ["sin molestias", "sin lesiones", "no tengo molestias", "no tengo lesiones"]):
            fields["physical_limitations"] = None
            fields["sensitive_data_acknowledged"] = True
        elif any(marker in text for marker in ["dolor", "lesion", "molestia", "rodilla", "hombro", "espalda"]):
            if profile.sensitive_data_acknowledged:
                fields["physical_limitations"] = message[:700]
        return fields

    def _extract_numbers(self, text: str, fields: dict[str, Any]) -> None:
        patterns = [
            ("age", r"\b(1[4-9]|[2-8][0-9]|90)\s*(anos|anio|years|edad)\b"),
            ("height_cm", r"\b(1[2-9][0-9]|2[0-2][0-9]|230)\s*(cm|centimetros)\b"),
            ("weight_kg", r"\b(3[5-9]|[4-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|250)\s*(kg|kilos)\b"),
            ("days_per_week", r"\b([1-7])\s*(dias|dia|days)\b"),
            ("session_duration_minutes", r"\b(2[0-9]|[3-9][0-9]|1[0-7][0-9]|180)\s*(min|mins|minutos)\b"),
        ]
        for field, pattern in patterns:
            match = re.search(pattern, text)
            if match:
                fields[field] = int(match.group(1))

    def _extract_lists(self, text: str, fields: dict[str, Any]) -> None:
        if any(marker in text for marker in ["gimnasio completo", "gym completo", "gimnasio comercial", "tengo todo"]):
            fields["equipment"] = EQUIPMENT_FULL_GYM
        else:
            equipment = [item for item in ["mancuernas", "barra", "banco", "polea", "maquina", "bandas", "peso corporal"] if item in text]
            if equipment:
                fields["equipment"] = equipment
        priorities = [item for item in ["pecho", "espalda", "pierna", "hombro", "gluteo", "brazos", "core", "cardio"] if item in text]
        if priorities:
            fields["priorities"] = priorities
        avoided = []
        for marker in ["peso muerto", "sentadilla", "press banca", "dominadas", "correr"]:
            if f"sin {marker}" in text or f"evitar {marker}" in text or f"no quiero {marker}" in text:
                avoided.append(marker)
        if avoided:
            fields["avoided_exercises"] = avoided

    def _apply_fields(self, profile: CoachProfile, fields: dict[str, Any]) -> list[str]:
        changed: list[str] = []
        scalar_fields = {
            "goal",
            "biological_sex",
            "age",
            "height_cm",
            "weight_kg",
            "experience_level",
            "days_per_week",
            "session_duration_minutes",
            "personal_data_acknowledged",
            "sensitive_data_acknowledged",
            "physical_limitations",
        }
        list_fields = {"equipment", "priorities", "preferred_exercises", "avoided_exercises"}
        for field, value in fields.items():
            if field in scalar_fields and getattr(profile, field) != value:
                setattr(profile, field, value)
                changed.append(field)
            elif field in list_fields:
                current = set(getattr(profile, field) or [])
                merged = sorted(current | {str(item).strip() for item in value if str(item).strip()})
                if merged != getattr(profile, field):
                    setattr(profile, field, merged)
                    changed.append(field)
        return changed

    def _assistant_response(self, profile: CoachProfile, changed: list[str]) -> str:
        confirmations = [self._field_confirmation(field, profile) for field in changed]
        confirmations = [item for item in confirmations if item]
        missing = self._missing_required_fields(profile)
        prefix = " ".join(confirmations)
        if missing:
            return f"{prefix} {self._question_text(missing[0])}".strip()
        return f"{prefix} Ya tengo lo necesario para disenar tu plan. Puedes crear un borrador revisable o decirme prioridades, ejercicios a evitar o molestias confirmando el aviso medico.".strip()

    def _assistant_prompt(self, profile: CoachProfile) -> str:
        missing = self._missing_required_fields(profile)
        if missing:
            return self._question_text(missing[0])
        return "Perfil listo. Puedo crear un plan revisable con split, volumen, progresion y ejercicios justificados."

    def _question_text(self, field: str) -> str:
        questions = {
            "personal_data_acknowledged": "Para personalizar el plan necesito que confirmes el aviso de datos personales. No usare email, usuario, tokens ni notas privadas.",
            "goal": "Cual es tu objetivo principal: fuerza, hipertrofia, perder grasa, salud general o resistencia?",
            "biological_sex": "Cual es tu sexo biologico para ajustar referencias de entrenamiento: masculino o femenino?",
            "age": "Que edad tienes?",
            "height_cm": "Cuanto mides en centimetros?",
            "weight_kg": "Cuanto pesas en kg?",
            "experience_level": "Cual es tu nivel entrenando: principiante, intermedio o avanzado?",
            "days_per_week": "Cuantos dias por semana puedes entrenar?",
            "session_duration_minutes": "Cuantos minutos tendra cada sesion?",
            "equipment": "Que equipamiento tienes: gimnasio completo, mancuernas, barra, banco, polea, maquinas, bandas o peso corporal?",
        }
        return questions[field]

    def _field_confirmation(self, field: str, profile: CoachProfile) -> str | None:
        labels = {
            "goal": f"Objetivo guardado: {profile.goal}.",
            "biological_sex": f"Sexo biologico guardado: {profile.biological_sex}.",
            "age": f"Edad guardada: {profile.age}.",
            "height_cm": f"Altura guardada: {profile.height_cm} cm.",
            "weight_kg": f"Peso guardado: {profile.weight_kg} kg.",
            "experience_level": f"Nivel guardado: {profile.experience_level}.",
            "days_per_week": f"Disponibilidad guardada: {profile.days_per_week} dias.",
            "session_duration_minutes": f"Duracion guardada: {profile.session_duration_minutes} min.",
            "equipment": "Equipamiento guardado.",
            "priorities": "Prioridades guardadas.",
            "avoided_exercises": "Ejercicios a evitar guardados.",
            "personal_data_acknowledged": "Aviso de datos personales confirmado.",
            "sensitive_data_acknowledged": "Aviso medico confirmado.",
            "physical_limitations": "Limitaciones guardadas.",
        }
        return labels.get(field)

    def _plan_priorities(self, profile: CoachProfile) -> list[str]:
        priorities = list(profile.priorities or [])
        priorities.extend([f"preferir {item}" for item in profile.preferred_exercises or []])
        priorities.extend([f"evitar {item}" for item in profile.avoided_exercises or []])
        return priorities[:12]

    def _coach_brief(self, profile: CoachProfile) -> dict[str, Any]:
        return {
            "source": COACH_SOURCE,
            "biological_sex": profile.biological_sex,
            "age": profile.age,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
            "secondary_goal": profile.secondary_goal,
            "training_age_months": profile.training_age_months,
            "preferred_exercises": profile.preferred_exercises,
            "avoided_exercises": profile.avoided_exercises,
            "sleep_quality": profile.sleep_quality,
            "stress_level": profile.stress_level,
            "current_fatigue": profile.current_fatigue,
            "memory_summary": profile.memory_summary,
        }

    def _summary(self, profile: CoachProfile) -> str:
        return (
            f"Objetivo={profile.goal or 'pendiente'}; nivel={profile.experience_level or 'pendiente'}; "
            f"dias={profile.days_per_week or 'pendiente'}; duracion={profile.session_duration_minutes or 'pendiente'}; "
            f"equipo={', '.join(profile.equipment or []) or 'pendiente'}; prioridades={', '.join(profile.priorities or []) or 'ninguna'}; "
            f"evitar={', '.join(profile.avoided_exercises or []) or 'ninguno'}."
        )

    def _recent_messages(self, current: list[dict[str, str]], user_message: str, assistant_message: str) -> list[dict[str, str]]:
        messages = [*(current or []), {"role": "user", "content": user_message}, {"role": "assistant", "content": assistant_message}]
        return messages[-12:]

    def _next_action(self, missing: list[str], draft_plans: list[AiTrainingPlan], accepted_plan: AiTrainingPlan | None) -> str:
        if accepted_plan is not None:
            return "train"
        if draft_plans:
            return "review_plan"
        if missing:
            return "answer_profile_question"
        return "generate_plan"

    def _normalize(self, value: str) -> str:
        return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


coach_service = CoachService()
