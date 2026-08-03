import re
import unicodedata
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.ai_training_plan_service import AiTrainingPlanCannotGenerateError, ai_training_plan_service
from app.domain.ai import CoachV2MessageRead, CoachV2MessageRequest, CoachV2StateRead, AiTrainingPlanGenerateRequest
from app.infrastructure.db.models.ai import CoachConversation, CoachProfile, CoachProposal
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.coach_v2 import CoachV2Repository
from app.infrastructure.db.repositories.routines import WorkoutSessionRepository
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
GOALS = {"strength", "hypertrophy", "fat_loss", "general_health", "endurance"}
LEVELS = {"beginner", "intermediate", "advanced"}
EQUIPMENT_FULL_GYM = ["mancuernas", "barra", "banco", "polea", "maquina", "peso corporal"]


class CoachV2CannotGenerateError(Exception):
    pass


class CoachV2ProposalNotFoundError(Exception):
    pass


class CoachV2ProposalNotPendingError(Exception):
    pass


class CoachV2Service:
    def get_state(self, db: Session, user: User) -> CoachV2StateRead:
        repository = CoachV2Repository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        self._refresh_phase(profile, conversation)
        self._maybe_create_automatic_proposal(db, repository, user.id)
        db.commit()
        return self._state(repository, profile, conversation, self._question_for(profile, conversation))

    def add_message(self, db: Session, user: User, data: CoachV2MessageRequest) -> CoachV2StateRead:
        repository = CoachV2Repository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        if data.personal_data_acknowledged:
            profile.personal_data_acknowledged = True
        if data.sensitive_data_acknowledged:
            profile.sensitive_data_acknowledged = True

        extracted = self._extract_fields(data.message, profile, conversation)
        changed = self._apply_fields(profile, extracted)
        assistant_message, next_question = self._assistant_response(data.message, profile, conversation, changed)
        conversation.last_question = next_question
        self._refresh_phase(profile, conversation)
        conversation.recent_messages = self._recent_messages(conversation.recent_messages, data.message, assistant_message)
        conversation.conversation_summary = self._summary(profile)
        profile.memory_summary = self._summary(profile)
        self._store_memory(repository, user.id, changed)
        self._maybe_create_intent_proposal(repository, user.id, data.message)
        db.commit()
        return self._state(repository, profile, conversation, assistant_message)

    def generate_plan(self, db: Session, user: User):
        repository = CoachV2Repository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        missing = self._missing_required_fields(profile)
        if missing:
            raise CoachV2CannotGenerateError("Coach profile is missing required fields.")
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
            plan = ai_training_plan_service.generate_plan(db, user, request)
        except AiTrainingPlanCannotGenerateError as error:
            raise CoachV2CannotGenerateError(str(error)) from error
        repository.add_memory(user_id=user.id, event_type="plan_generated", summary="Coach V2 genero un plan borrador revisable.", payload={"plan_id": str(plan.id), "goal": profile.goal})
        conversation.phase = "plan_ready"
        db.commit()
        return plan

    def generate_planned_session(self, db: Session, user: User):
        repository = CoachV2Repository(db)
        plans = AiTrainingPlanRepository(db).list_by_user(user.id)
        plan = next((item for item in plans if item.status in {"accepted", "draft"}), None)
        if plan is None:
            raise CoachV2CannotGenerateError("Generate a training plan before creating a planned session.")
        routine = (plan.plan_payload.get("routines") or [{}])[0]
        exercises = routine.get("exercises") if isinstance(routine, dict) else []
        payload = {
            "source_plan_id": str(plan.id),
            "goal": plan.goal,
            "routine_name": routine.get("name", "Sesion recomendada") if isinstance(routine, dict) else "Sesion recomendada",
            "exercises": exercises[:8] if isinstance(exercises, list) else [],
        }
        planned = repository.create_planned_session(
            user_id=user.id,
            title=f"Proxima sesion: {payload['routine_name']}",
            session_payload=payload,
            rationale="Sesion recomendada desde el plan actual. Ajusta cargas usando tecnica estable y RIR objetivo.",
        )
        db.commit()
        return planned

    def reset(self, db: Session, user: User) -> CoachV2StateRead:
        repository = CoachV2Repository(db)
        profile, conversation = repository.reset(user.id)
        db.commit()
        return self._state(repository, profile, conversation, self._question_for(profile, conversation))

    def accept_proposal(self, db: Session, proposal_id: UUID, user: User) -> CoachProposal:
        return self._review_proposal(db, proposal_id, user, "accepted")

    def reject_proposal(self, db: Session, proposal_id: UUID, user: User) -> CoachProposal:
        return self._review_proposal(db, proposal_id, user, "rejected")

    def _review_proposal(self, db: Session, proposal_id: UUID, user: User, status: str) -> CoachProposal:
        repository = CoachV2Repository(db)
        proposal = repository.get_proposal(proposal_id, user.id)
        if proposal is None:
            raise CoachV2ProposalNotFoundError
        if proposal.status != "pending":
            raise CoachV2ProposalNotPendingError
        repository.review_proposal(proposal, status)
        db.commit()
        return proposal

    def _extract_fields(self, message: str, profile: CoachProfile, conversation: CoachConversation) -> dict[str, Any]:
        text = self._normalize(message)
        fields: dict[str, Any] = {}
        if any(marker in text for marker in ["acepto", "confirmo", "ok", "si", "sí", "de acuerdo", "entiendo"]):
            if conversation.last_question in {None, "personal_data_acknowledged"} or "datos" in text or "aviso" in text:
                fields["personal_data_acknowledged"] = True
        if any(marker in text for marker in ["fuerza", "strength"]):
            fields["goal"] = "strength"
        elif any(marker in text for marker in ["hipertrof", "musculo", "masa muscular", "volumen"]):
            fields["goal"] = "hypertrophy"
        elif any(marker in text for marker in ["perder grasa", "perdida de grasa", "adelgazar", "definir", "grasa"]):
            fields["goal"] = "fat_loss"
        elif any(marker in text for marker in ["salud", "general", "bienestar"]):
            fields["goal"] = "general_health"
        elif any(marker in text for marker in ["resistencia", "cardio", "endurance"]):
            fields["goal"] = "endurance"

        if "masculino" in text or text == "hombre" or text == "male":
            fields["biological_sex"] = "male"
        if "femenino" in text or text == "mujer" or text == "female":
            fields["biological_sex"] = "female"
        if any(marker in text for marker in ["principiante", "novato", "beginner"]):
            fields["experience_level"] = "beginner"
        elif any(marker in text for marker in ["intermedio", "intermediate"]):
            fields["experience_level"] = "intermediate"
        elif any(marker in text for marker in ["avanzado", "advanced"]):
            fields["experience_level"] = "advanced"

        numbers = [int(item) for item in re.findall(r"\b\d{1,3}\b", text)]
        for value in numbers:
            if conversation.last_question == "age" and 12 <= value <= 90:
                fields["age"] = value
            elif conversation.last_question == "height_cm" and 120 <= value <= 230:
                fields["height_cm"] = value
            elif conversation.last_question == "weight_kg" and 35 <= value <= 250:
                fields["weight_kg"] = value
            elif conversation.last_question == "days_per_week" and 1 <= value <= 7:
                fields["days_per_week"] = value
            elif conversation.last_question == "session_duration_minutes" and 20 <= value <= 180:
                fields["session_duration_minutes"] = value
        self._extract_labeled_numbers(text, fields)

        if any(marker in text for marker in ["gimnasio comercial", "gym comercial", "gimnasio completo", "tengo todo", "gym completo"]):
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
        if any(marker in text for marker in ["sin molestias", "no tengo molestias", "no tengo lesiones", "sin lesiones"]):
            fields["physical_limitations"] = None
            fields["sensitive_data_acknowledged"] = True
        elif any(marker in text for marker in ["dolor", "lesion", "molestia", "rodilla", "hombro", "espalda"]):
            if profile.sensitive_data_acknowledged:
                fields["physical_limitations"] = message[:700]
        return fields

    def _extract_labeled_numbers(self, text: str, fields: dict[str, Any]) -> None:
        patterns = [
            ("age", r"(\d{2})\s*(anos|años)"),
            ("height_cm", r"(1[2-9][0-9]|2[0-2][0-9]|230)\s*(cm|centimetros)"),
            ("weight_kg", r"(3[5-9]|[4-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|250)\s*(kg|kilos)"),
            ("days_per_week", r"\b([1-7])\s*(dias|días|days)"),
            ("session_duration_minutes", r"(2[0-9]|[3-9][0-9]|1[0-7][0-9]|180)\s*(min|mins|minutos)"),
        ]
        for field, pattern in patterns:
            match = re.search(pattern, text)
            if match:
                fields[field] = int(match.group(1))

    def _apply_fields(self, profile: CoachProfile, fields: dict[str, Any]) -> list[str]:
        changed: list[str] = []
        for field, value in fields.items():
            if field in {"goal", "biological_sex", "age", "height_cm", "weight_kg", "experience_level", "days_per_week", "session_duration_minutes", "personal_data_acknowledged", "sensitive_data_acknowledged", "physical_limitations"}:
                if getattr(profile, field) != value:
                    setattr(profile, field, value)
                    changed.append(field)
            elif field in {"equipment", "priorities", "avoided_exercises"}:
                current = set(getattr(profile, field) or [])
                merged = sorted(current | {str(item) for item in value if str(item).strip()})
                if merged != getattr(profile, field):
                    setattr(profile, field, merged)
                    changed.append(field)
        return changed

    def _assistant_response(self, user_message: str, profile: CoachProfile, conversation: CoachConversation, changed: list[str]) -> tuple[str, str | None]:
        missing = self._missing_required_fields(profile)
        confirmations = [self._field_confirmation(field, profile) for field in changed]
        confirmations = [item for item in confirmations if item]
        if missing:
            next_field = missing[0]
            question = self._question_text(next_field)
            prefix = " ".join(confirmations)
            return (f"{prefix} {question}".strip(), next_field)
        if self._wants_generation(user_message):
            return "Ya tengo los datos obligatorios. Pulsa Generar plan y creare un borrador revisable con progresion, volumen e intensidad ajustados a tu objetivo.", None
        prefix = " ".join(confirmations) or "Perfil completo."
        return f"{prefix} Ya puedo crear un plan cientifico y revisable. Si quieres, antes puedes decirme prioridades, ejercicios a evitar o molestias confirmando el aviso medico.", None

    def _field_confirmation(self, field: str, profile: CoachProfile) -> str | None:
        values = {
            "goal": f"Objetivo anotado: {profile.goal}.",
            "biological_sex": f"Sexo biologico anotado: {'masculino' if profile.biological_sex == 'male' else 'femenino'}.",
            "age": f"Edad anotada: {profile.age} anos.",
            "height_cm": f"Altura anotada: {profile.height_cm} cm.",
            "weight_kg": f"Peso anotado: {profile.weight_kg} kg.",
            "experience_level": f"Nivel anotado: {profile.experience_level}.",
            "days_per_week": f"Disponibilidad anotada: {profile.days_per_week} dias/semana.",
            "session_duration_minutes": f"Duracion anotada: {profile.session_duration_minutes} min/sesion.",
            "equipment": f"Equipamiento anotado: {', '.join(profile.equipment)}.",
            "priorities": f"Prioridades anotadas: {', '.join(profile.priorities)}.",
            "avoided_exercises": f"Evitare: {', '.join(profile.avoided_exercises)}.",
        }
        return values.get(field)

    def _question_for(self, profile: CoachProfile, conversation: CoachConversation) -> str:
        missing = self._missing_required_fields(profile)
        if missing:
            conversation.last_question = missing[0]
            return self._question_text(missing[0])
        return "Tu perfil esta completo. Puedo generar un plan revisable o revisar tu progreso, fatiga y proxima sesion."

    def _question_text(self, field: str) -> str:
        questions = {
            "personal_data_acknowledged": "Para crear un plan cientifico necesito usar datos personales: sexo biologico, edad, altura y peso. Se usan solo para personalizar entrenamiento y Zenith no sustituye consejo medico. Responde 'acepto' para continuar.",
            "goal": "Cual es tu objetivo principal: fuerza, hipertrofia, perdida de grasa, salud general o resistencia?",
            "biological_sex": "Indica tu sexo biologico: masculino o femenino.",
            "age": "Que edad tienes?",
            "height_cm": "Cuanto mides en centimetros?",
            "weight_kg": "Cuanto pesas en kg?",
            "experience_level": "Cual es tu nivel real entrenando: principiante, intermedio o avanzado?",
            "days_per_week": "Cuantos dias por semana puedes entrenar de forma constante?",
            "session_duration_minutes": "Cuantos minutos tienes por sesion?",
            "equipment": "Entrenas en gimnasio comercial, en casa o con que equipamiento cuentas?",
        }
        return questions[field]

    def _missing_required_fields(self, profile: CoachProfile) -> list[str]:
        missing = []
        for field in REQUIRED_PROFILE_FIELDS:
            value = getattr(profile, field)
            if value in (None, "", []) or value is False:
                missing.append(field)
        return missing

    def _refresh_phase(self, profile: CoachProfile, conversation: CoachConversation) -> None:
        if self._missing_required_fields(profile):
            conversation.phase = "onboarding"
        elif conversation.phase == "onboarding":
            conversation.phase = "plan_ready"

    def _state(self, repository: CoachV2Repository, profile: CoachProfile, conversation: CoachConversation, assistant_message: str) -> CoachV2StateRead:
        missing = self._missing_required_fields(profile)
        return CoachV2StateRead(
            profile=profile,
            conversation={
                "id": conversation.id,
                "user_id": conversation.user_id,
                "phase": conversation.phase,
                "last_question": conversation.last_question,
                "recent_messages": [CoachV2MessageRead(**item) for item in conversation.recent_messages],
                "conversation_summary": conversation.conversation_summary,
                "updated_at": conversation.updated_at,
            },
            assistant_message=assistant_message,
            missing_required_fields=missing,
            ready_for_plan=not missing,
            memory_events=repository.list_memory(profile.user_id),
            proposals=repository.list_proposals(profile.user_id),
            planned_sessions=repository.list_planned_sessions(profile.user_id),
            privacy_notice="Zenith usa estos datos para personalizar entrenamiento. No sustituye consejo medico ni profesional.",
            next_action="generate_plan" if not missing else "answer_question",
        )

    def _recent_messages(self, current: list[dict[str, Any]], user_message: str, assistant_message: str) -> list[dict[str, Any]]:
        messages = [*list(current or []), {"role": "user", "content": user_message[:700]}, {"role": "assistant", "content": assistant_message[:900]}]
        return messages[-10:]

    def _summary(self, profile: CoachProfile) -> str:
        parts = [
            f"objetivo {profile.goal}" if profile.goal else None,
            f"sexo biologico {profile.biological_sex}" if profile.biological_sex else None,
            f"{profile.age} anos" if profile.age else None,
            f"{profile.height_cm} cm" if profile.height_cm else None,
            f"{profile.weight_kg} kg" if profile.weight_kg else None,
            f"nivel {profile.experience_level}" if profile.experience_level else None,
            f"{profile.days_per_week} dias/semana" if profile.days_per_week else None,
            f"{profile.session_duration_minutes} min/sesion" if profile.session_duration_minutes else None,
            f"equipo: {', '.join(profile.equipment)}" if profile.equipment else None,
            f"prioridades: {', '.join(profile.priorities)}" if profile.priorities else None,
            f"evitar: {', '.join(profile.avoided_exercises)}" if profile.avoided_exercises else None,
        ]
        return "; ".join(item for item in parts if item)

    def _store_memory(self, repository: CoachV2Repository, user_id: UUID, changed: list[str]) -> None:
        important = [field for field in changed if field in {"goal", "biological_sex", "equipment", "priorities", "avoided_exercises", "physical_limitations"}]
        for field in important:
            repository.add_memory(user_id=user_id, event_type="profile_update", summary=f"Actualizado {field} en perfil Coach.", payload={"field": field})

    def _maybe_create_intent_proposal(self, repository: CoachV2Repository, user_id: UUID, message: str) -> None:
        text = self._normalize(message)
        if any(marker in text for marker in ["reventado", "agotado", "muy cansado", "fatiga", "no progreso", "estancado"]):
            repository.create_proposal(
                user_id=user_id,
                type="fatigue_review",
                recommendation="Revisar fatiga y considerar descarga parcial o reduccion temporal de volumen.",
                explanation="El mensaje indica fatiga o estancamiento. El Coach debe revisar sesiones recientes, RPE/RIR y caidas de reps antes de aplicar cambios.",
                payload={"source": "conversation_intent"},
            )

    def _maybe_create_automatic_proposal(self, db: Session, repository: CoachV2Repository, user_id: UUID) -> None:
        pending = [proposal for proposal in repository.list_proposals(user_id) if proposal.status == "pending" and proposal.type == "progress_review"]
        if pending:
            return
        sessions = WorkoutSessionRepository(db).list_by_user(user_id)
        if len(sessions) >= 3:
            repository.create_proposal(
                user_id=user_id,
                type="progress_review",
                recommendation="Revisar progreso de las ultimas sesiones y preparar ajustes si hay fatiga o estancamiento.",
                explanation="Hay suficiente historial reciente para una revision automatica del Coach.",
                payload={"recent_session_count": min(len(sessions), 5)},
            )

    def _plan_priorities(self, profile: CoachProfile) -> list[str]:
        priorities = list(profile.priorities)
        if profile.goal == "fat_loss" and "mantener masa muscular" not in priorities:
            priorities.append("mantener masa muscular")
        if profile.goal == "endurance" and "resistencia cardiovascular" not in priorities:
            priorities.append("resistencia cardiovascular")
        if profile.avoided_exercises:
            priorities.extend([f"evitar {item}" for item in profile.avoided_exercises])
        return priorities[:10]

    def _wants_generation(self, message: str) -> bool:
        text = self._normalize(message)
        return any(marker in text for marker in ["genera", "haz el plan", "adelante", "crea el plan", "vamos"])

    def _normalize(self, value: str) -> str:
        return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()


coach_v2_service = CoachV2Service()
