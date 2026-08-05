import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.ai_provider import AiProviderError, CoachEvidenceQueryProviderContext, CoachInterviewProviderContext, build_ai_provider
from app.application.ai_training_plan_service import (
    AiTrainingPlanCannotGenerateError,
    AiTrainingPlanNotDraftError,
    AiTrainingPlanNotFoundError,
    ai_training_plan_service,
)
from app.application.evidence_search_service import evidence_search_service
from app.domain.ai import (
    AiTrainingPlanGenerateRequest,
    AiTrainingPlanModifyRequest,
    CoachMessageRequest,
    CoachPlanDraftReviseRequest,
    CoachStateRead,
)
from app.infrastructure.db.models.ai import AiTrainingPlan, CoachConversation, CoachProfile
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.coach import CoachRepository
from app.infrastructure.db.repositories.training_plans import AiTrainingPlanRepository

CRITICAL_FIELDS = [
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

USEFUL_FIELDS = [
    "training_age_months",
    "available_weekdays",
    "training_location",
    "current_routine",
    "recent_results",
    "main_lifts",
    "priorities",
    "lagging_muscles",
    "well_developed_muscles",
    "preferred_exercises",
    "avoided_exercises",
    "physical_limitations",
    "sleep_quality",
    "stress_level",
    "current_fatigue",
    "nutrition_current",
    "willing_to_track_nutrition",
    "timeline_goal",
    "weeks_with_limited_training",
    "tracking_method",
]

GOALS = {"strength", "hypertrophy", "fat_loss", "general_health", "endurance"}
SEXES = {"male", "female"}
LEVELS = {"beginner", "intermediate", "advanced"}
PHASES = {"onboarding", "ready_for_plan", "plan_draft", "training_active"}
PLAN_CREATED_BY = "coach"


class CoachCannotGenerateError(Exception):
    pass


class CoachPlanNotFoundError(Exception):
    pass


class CoachPlanNotDraftError(Exception):
    pass


class CoachService:
    def get_state(self, db: Session, user: User) -> CoachStateRead:
        repository = CoachRepository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        state = self._load_interview_state(conversation)
        assistant_message = self._initial_message(profile, state)
        return self._state(db, user.id, profile, conversation, assistant_message, state)

    def add_message(self, db: Session, user: User, data: CoachMessageRequest) -> CoachStateRead:
        repository = CoachRepository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        state = self._load_interview_state(conversation)

        if data.personal_data_acknowledged:
            profile.personal_data_acknowledged = True
        if data.sensitive_data_acknowledged:
            profile.sensitive_data_acknowledged = True

        missing_critical = self._missing_critical(profile)
        provider = build_ai_provider()
        context = CoachInterviewProviderContext(
            profile=self._profile_snapshot(profile, state),
            interview_state=state,
            recent_messages=conversation.recent_messages or [],
            user_message=data.message,
            personal_data_acknowledged=profile.personal_data_acknowledged,
            sensitive_data_acknowledged=profile.sensitive_data_acknowledged,
            missing_critical=missing_critical,
            missing_useful=self._missing_useful(profile, state),
        )
        try:
            result = provider.build_coach_interview_response(context)
        except (AttributeError, AiProviderError) as error:
            raise CoachCannotGenerateError("Coach AI interview failed.") from error

        changed = self._apply_profile_updates(profile, state, result.profile_updates)
        state = self._updated_interview_state(state, result, changed)
        missing_critical = self._missing_critical(profile)
        if missing_critical:
            state["missing_critical"] = missing_critical
            state["ready_for_plan"] = False
        else:
            state["missing_critical"] = []
            state["ready_for_plan"] = bool(result.ready_for_plan)
        state["missing_useful"] = self._merge_unique(result.missing_useful, self._missing_useful(profile, state))[:20]

        conversation.recent_messages = self._recent_messages(conversation.recent_messages, data.message, result.assistant_message)
        conversation.conversation_summary = json.dumps(state, ensure_ascii=False)
        conversation.phase = self._phase(db, user.id, profile, state)
        profile.memory_summary = self._memory_summary(profile, state)
        if changed:
            repository.add_memory(
                user_id=user.id,
                event_type="profile_updated",
                summary=f"Coach actualizo perfil: {', '.join(changed)}.",
                payload={"fields": changed},
            )
        db.commit()
        return self._state(db, user.id, profile, conversation, result.assistant_message, state)

    def generate_plan_draft(self, db: Session, user: User) -> AiTrainingPlan:
        repository = CoachRepository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        state = self._load_interview_state(conversation)
        missing = self._missing_critical(profile)
        if missing or not state.get("ready_for_plan"):
            raise CoachCannotGenerateError("Coach interview is missing critical data.")
        request = AiTrainingPlanGenerateRequest(
            goal=profile.goal,
            level=profile.experience_level,
            days_per_week=profile.days_per_week,
            session_duration_minutes=profile.session_duration_minutes,
            available_equipment=profile.equipment,
            physical_limitations=profile.physical_limitations if profile.sensitive_data_acknowledged else None,
            sensitive_data_acknowledged=profile.sensitive_data_acknowledged,
            priorities=self._plan_priorities(profile, state),
        )
        evidence = self._collect_evidence(profile, state, revision_requested=False)
        coach_brief = self._coach_brief(profile, state, evidence=evidence)
        try:
            plan = ai_training_plan_service.generate_plan(
                db,
                user,
                request,
                require_ai_provider=True,
                coach_brief=coach_brief,
            )
        except AiTrainingPlanCannotGenerateError as error:
            raise CoachCannotGenerateError(str(error)) from error
        self._mark_coach_plan(plan, state, evidence)
        conversation.phase = "plan_draft"
        repository.add_memory(
            user_id=user.id,
            event_type="plan_draft_generated",
            summary="Coach genero una vista previa de plan revisable.",
            payload={"plan_id": str(plan.id)},
        )
        db.commit()
        return plan

    def accept_plan_draft(self, db: Session, plan_id: UUID, user: User) -> AiTrainingPlan:
        self._get_coach_plan(db, plan_id, user.id)
        try:
            plan = ai_training_plan_service.accept_plan(db, plan_id, user)
        except AiTrainingPlanNotFoundError as error:
            raise CoachPlanNotFoundError from error
        except AiTrainingPlanNotDraftError as error:
            raise CoachPlanNotDraftError from error
        except AiTrainingPlanCannotGenerateError as error:
            raise CoachCannotGenerateError(str(error)) from error
        repository = CoachRepository(db)
        conversation = repository.get_or_create_conversation(user.id)
        conversation.phase = "training_active"
        repository.add_memory(
            user_id=user.id,
            event_type="plan_draft_accepted",
            summary="Coach aplico el plan aceptado y creo rutinas reales.",
            payload={"plan_id": str(plan.id)},
        )
        db.commit()
        return plan

    def reject_plan_draft(self, db: Session, plan_id: UUID, user: User) -> AiTrainingPlan:
        self._get_coach_plan(db, plan_id, user.id)
        try:
            plan = ai_training_plan_service.reject_plan(db, plan_id, user)
        except AiTrainingPlanNotFoundError as error:
            raise CoachPlanNotFoundError from error
        except AiTrainingPlanNotDraftError as error:
            raise CoachPlanNotDraftError from error
        db.commit()
        return plan

    def revise_plan_draft(self, db: Session, plan_id: UUID, user: User, data: CoachPlanDraftReviseRequest) -> AiTrainingPlan:
        original = self._get_coach_plan(db, plan_id, user.id)
        repository = CoachRepository(db)
        profile = repository.get_or_create_profile(user.id)
        conversation = repository.get_or_create_conversation(user.id)
        state = self._load_interview_state(conversation)
        needs_evidence = self._revision_needs_evidence(data.instruction)
        evidence = self._collect_evidence(profile, state, revision_requested=True) if needs_evidence else dict(original.plan_payload.get("evidence") or {})
        try:
            plan = ai_training_plan_service.modify_plan(
                db,
                plan_id,
                user,
                AiTrainingPlanModifyRequest(
                    instruction=data.instruction,
                    sensitive_data_acknowledged=data.sensitive_data_acknowledged,
                ),
                coach_brief=self._coach_brief(profile, state, evidence=evidence),
            )
        except AiTrainingPlanNotFoundError as error:
            raise CoachPlanNotFoundError from error
        except AiTrainingPlanNotDraftError as error:
            raise CoachPlanNotDraftError from error
        except AiTrainingPlanCannotGenerateError as error:
            raise CoachCannotGenerateError(str(error)) from error
        plan.input_summary = {
            **dict(plan.input_summary or {}),
            "created_by": PLAN_CREATED_BY,
            "revised_from_plan_id": str(original.id),
            "revision_instruction": data.instruction,
        }
        if evidence:
            plan.input_summary["evidence"] = evidence
        plan.plan_payload = {**dict(plan.plan_payload or {}), "source": PLAN_CREATED_BY, "schema_version": 1, "evidence": evidence}
        db.commit()
        return plan

    def reset(self, db: Session, user: User) -> CoachStateRead:
        repository = CoachRepository(db)
        profile, conversation = repository.reset(user.id)
        state = self._empty_interview_state()
        conversation.conversation_summary = json.dumps(state, ensure_ascii=False)
        conversation.phase = "onboarding"
        db.commit()
        return self._state(db, user.id, profile, conversation, self._initial_message(profile, state), state)

    def _state(
        self,
        db: Session,
        user_id: UUID,
        profile: CoachProfile,
        conversation: CoachConversation,
        assistant_message: str,
        state: dict[str, Any],
    ) -> CoachStateRead:
        plans = self._coach_plans(db, user_id)
        draft_plans = [plan for plan in plans if plan.status == "draft"]
        accepted_plan = next((plan for plan in plans if plan.status == "accepted"), None)
        missing_critical = self._missing_critical(profile)
        phase = self._phase_from_plans(profile, state, draft_plans, accepted_plan)
        conversation.phase = phase
        db.flush()
        return CoachStateRead(
            profile=profile,
            phase=phase,
            recent_messages=conversation.recent_messages or [],
            assistant_message=assistant_message,
            known_facts=self._string_list_state(state, "known_facts"),
            missing_critical=missing_critical,
            missing_useful=self._string_list_state(state, "missing_useful"),
            estimated_fields=self._string_list_state(state, "estimated_fields"),
            misunderstanding_corrections=self._string_list_state(state, "misunderstanding_corrections"),
            safety_flags=self._string_list_state(state, "safety_flags"),
            ready_for_plan=not missing_critical and bool(state.get("ready_for_plan")),
            draft_plans=draft_plans,
            accepted_plan=accepted_plan,
            privacy_notice="El Coach no usa email, usuario, tokens, credenciales, notas privadas ni historial completo. Solo guarda perfil estructurado, resumen y ultimos mensajes necesarios.",
            safety_notice="No diagnostica ni sustituye consejo medico. Dolor, lesiones o limitaciones solo se guardan si confirmas el aviso medico.",
            next_action=self._next_action(missing_critical, draft_plans, accepted_plan, state),
        )

    def _phase(self, db: Session, user_id: UUID, profile: CoachProfile, state: dict[str, Any]) -> str:
        plans = self._coach_plans(db, user_id)
        return self._phase_from_plans(
            profile,
            state,
            [plan for plan in plans if plan.status == "draft"],
            next((plan for plan in plans if plan.status == "accepted"), None),
        )

    def _phase_from_plans(
        self,
        profile: CoachProfile,
        state: dict[str, Any],
        draft_plans: list[AiTrainingPlan],
        accepted_plan: AiTrainingPlan | None,
    ) -> str:
        if accepted_plan is not None:
            return "training_active"
        if draft_plans:
            return "plan_draft"
        if not self._missing_critical(profile) and state.get("ready_for_plan"):
            return "ready_for_plan"
        return "onboarding"

    def _coach_plans(self, db: Session, user_id: UUID) -> list[AiTrainingPlan]:
        return [plan for plan in AiTrainingPlanRepository(db).list_by_user(user_id) if self._is_coach_plan(plan)]

    def _get_coach_plan(self, db: Session, plan_id: UUID, user_id: UUID) -> AiTrainingPlan:
        plan = AiTrainingPlanRepository(db).get_by_user(plan_id, user_id)
        if plan is None or not self._is_coach_plan(plan):
            raise CoachPlanNotFoundError
        return plan

    def _is_coach_plan(self, plan: AiTrainingPlan) -> bool:
        return plan.input_summary.get("created_by") == PLAN_CREATED_BY or plan.plan_payload.get("source") == PLAN_CREATED_BY

    def _mark_coach_plan(self, plan: AiTrainingPlan, state: dict[str, Any], evidence: dict[str, Any]) -> None:
        plan.input_summary = {
            **dict(plan.input_summary or {}),
            "created_by": PLAN_CREATED_BY,
            "known_facts": self._string_list_state(state, "known_facts"),
            "estimated_fields": self._string_list_state(state, "estimated_fields"),
            "evidence": evidence,
        }
        plan.plan_payload = {
            **dict(plan.plan_payload or {}),
            "source": PLAN_CREATED_BY,
            "schema_version": 1,
            "evidence": evidence,
            "scientific_evidence_policy": {
                "no_fabricated_references": True,
                "evidence_labels": ["solid", "moderate", "practical"],
            },
        }

    def _apply_profile_updates(self, profile: CoachProfile, state: dict[str, Any], updates: dict[str, Any]) -> list[str]:
        changed: list[str] = []
        for field, value in updates.items():
            cleaned = self._clean_update(field, value, profile)
            if cleaned is _SKIP:
                continue
            if field in _PROFILE_FIELDS:
                if getattr(profile, field) != cleaned:
                    setattr(profile, field, cleaned)
                    changed.append(field)
            elif field in _EXTRA_FIELDS:
                extra = dict(state.get("profile_extra") or {})
                if extra.get(field) != cleaned:
                    extra[field] = cleaned
                    state["profile_extra"] = extra
                    changed.append(field)
        return changed

    def _clean_update(self, field: str, value: Any, profile: CoachProfile):
        if field not in _PROFILE_FIELDS and field not in _EXTRA_FIELDS:
            return _SKIP
        if field == "physical_limitations" and not profile.sensitive_data_acknowledged:
            return _SKIP
        if field in {"goal", "secondary_goal"}:
            return value if isinstance(value, str) and value in GOALS else _SKIP
        if field == "biological_sex":
            return value if isinstance(value, str) and value in SEXES else _SKIP
        if field == "experience_level":
            return value if isinstance(value, str) and value in LEVELS else _SKIP
        if field == "age":
            return value if isinstance(value, int) and 14 <= value <= 90 else _SKIP
        if field == "height_cm":
            return value if isinstance(value, int) and 120 <= value <= 230 else _SKIP
        if field == "weight_kg":
            return value if isinstance(value, int) and 35 <= value <= 250 else _SKIP
        if field == "training_age_months":
            return value if isinstance(value, int) and 0 <= value <= 720 else _SKIP
        if field == "days_per_week":
            return value if isinstance(value, int) and 1 <= value <= 7 else _SKIP
        if field == "session_duration_minutes":
            return value if isinstance(value, int) and 20 <= value <= 180 else _SKIP
        if field in {"equipment", "priorities", "preferred_exercises", "avoided_exercises", "available_weekdays", "main_lifts", "lagging_muscles", "well_developed_muscles", "weeks_with_limited_training"}:
            return self._clean_list(value)
        if field in {"sleep_quality", "stress_level", "current_fatigue", "training_location", "current_routine", "recent_results", "nutrition_current", "willing_to_track_nutrition", "timeline_goal", "tracking_method", "body_fat_percent", "physical_limitations"}:
            return value.strip()[:1_000] if isinstance(value, str) and value.strip() else _SKIP
        return _SKIP

    def _clean_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        for item in value[:20]:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip()[:120])
        return sorted(set(cleaned))

    def _missing_critical(self, profile: CoachProfile) -> list[str]:
        missing: list[str] = []
        for field in CRITICAL_FIELDS:
            value = getattr(profile, field)
            if isinstance(value, list):
                if not value:
                    missing.append(field)
            elif value in {None, "", False}:
                missing.append(field)
        if not profile.personal_data_acknowledged:
            missing.insert(0, "personal_data_acknowledged")
        return missing

    def _missing_useful(self, profile: CoachProfile, state: dict[str, Any]) -> list[str]:
        extra = dict(state.get("profile_extra") or {})
        missing: list[str] = []
        for field in USEFUL_FIELDS:
            if field in _PROFILE_FIELDS:
                value = getattr(profile, field)
            else:
                value = extra.get(field)
            if isinstance(value, list):
                if not value:
                    missing.append(field)
            elif value in {None, "", False}:
                missing.append(field)
        return missing

    def _profile_snapshot(self, profile: CoachProfile, state: dict[str, Any]) -> dict[str, Any]:
        snapshot = {field: getattr(profile, field) for field in _PROFILE_FIELDS}
        snapshot["profile_extra"] = dict(state.get("profile_extra") or {})
        return snapshot

    def _updated_interview_state(self, state: dict[str, Any], result, changed: list[str]) -> dict[str, Any]:
        updated = dict(state)
        updated["known_facts"] = self._merge_unique(self._string_list_state(state, "known_facts"), result.known_facts)
        updated["missing_critical"] = result.missing_critical
        updated["missing_useful"] = result.missing_useful
        updated["estimated_fields"] = self._merge_unique(self._string_list_state(state, "estimated_fields"), result.estimated_fields)
        updated["misunderstanding_corrections"] = result.misunderstanding_corrections
        updated["safety_flags"] = result.safety_flags
        updated["ready_for_plan"] = result.ready_for_plan
        updated["next_questions"] = result.next_questions
        updated["last_updated_fields"] = changed
        updated["provider"] = result.provider
        updated["model"] = result.model
        return updated

    def _empty_interview_state(self) -> dict[str, Any]:
        return {
            "known_facts": [],
            "missing_critical": CRITICAL_FIELDS,
            "missing_useful": USEFUL_FIELDS,
            "estimated_fields": [],
            "misunderstanding_corrections": [],
            "safety_flags": [],
            "next_questions": [],
            "profile_extra": {},
            "ready_for_plan": False,
        }

    def _load_interview_state(self, conversation: CoachConversation) -> dict[str, Any]:
        if not conversation.conversation_summary:
            return self._empty_interview_state()
        try:
            parsed = json.loads(conversation.conversation_summary)
        except (TypeError, ValueError):
            return self._empty_interview_state()
        if not isinstance(parsed, dict):
            return self._empty_interview_state()
        return {**self._empty_interview_state(), **parsed}

    def _initial_message(self, profile: CoachProfile, state: dict[str, Any]) -> str:
        if not profile.personal_data_acknowledged:
            return "Actuo como tu entrenador IA. Antes de personalizar, confirma el uso de datos de entrenamiento; no uso email, usuario, tokens ni notas privadas. Despues empezamos por objetivo, edad/sexo, altura, peso y nivel."
        missing = self._missing_critical(profile)
        if missing:
            return "Voy a entrevistarte por bloques y no generare el plan hasta tener lo imprescindible. Cuéntame objetivo, edad/sexo, altura, peso, nivel, dias, duracion y equipamiento si aun falta algo."
        if state.get("ready_for_plan"):
            return "Tengo los datos imprescindibles. Puedo generar una vista previa del plan y luego la ajustamos antes de crear rutinas."
        return "Tengo muchos datos. Si quieres, seguimos afinando preferencias, molestias, sueño, nutricion y seguimiento antes de generar la vista previa."

    def _recent_messages(self, current: list[dict[str, str]], user_message: str, assistant_message: str) -> list[dict[str, str]]:
        messages = [*(current or []), {"role": "user", "content": user_message}, {"role": "assistant", "content": assistant_message}]
        return messages[-16:]

    def _memory_summary(self, profile: CoachProfile, state: dict[str, Any]) -> str:
        facts = "; ".join(self._string_list_state(state, "known_facts")[:8])
        return (
            f"Objetivo={profile.goal or 'pendiente'}; nivel={profile.experience_level or 'pendiente'}; "
            f"dias={profile.days_per_week or 'pendiente'}; duracion={profile.session_duration_minutes or 'pendiente'}; "
            f"equipo={', '.join(profile.equipment or []) or 'pendiente'}; hechos={facts or 'sin resumen'}"
        )

    def _plan_priorities(self, profile: CoachProfile, state: dict[str, Any]) -> list[str]:
        extra = dict(state.get("profile_extra") or {})
        priorities = list(profile.priorities or [])
        priorities.extend([f"preferir {item}" for item in profile.preferred_exercises or []])
        priorities.extend([f"evitar {item}" for item in profile.avoided_exercises or []])
        priorities.extend([f"priorizar {item}" for item in extra.get("lagging_muscles") or []])
        priorities.extend([f"datos utiles: {item}" for item in self._string_list_state(state, "known_facts")[:6]])
        return priorities[:20]

    def _coach_brief(self, profile: CoachProfile, state: dict[str, Any], *, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "created_by": PLAN_CREATED_BY,
            "profile": self._profile_snapshot(profile, state),
            "known_facts": self._string_list_state(state, "known_facts"),
            "estimated_fields": self._string_list_state(state, "estimated_fields"),
            "safety_flags": self._string_list_state(state, "safety_flags"),
            "evidence": evidence or {},
            "requirements": [
                "Generar vista previa profesional de 8-12 semanas antes de crear rutinas.",
                "Incluir justificacion cientifica sin inventar referencias.",
                "Distinguir evidencia solida, moderada y criterio practico.",
                "Permitir ejercicios fuera de base de datos como pendientes hasta aceptar.",
            ],
        }

    def _collect_evidence(self, profile: CoachProfile, state: dict[str, Any], *, revision_requested: bool) -> dict[str, Any]:
        if revision_requested is False and profile.goal is None:
            return {"search_queries": [], "used_references": [], "limitations": ["No se busco evidencia porque falta objetivo."], "errors": []}
        provider = build_ai_provider()
        context = CoachEvidenceQueryProviderContext(
            goal=profile.goal or "hypertrophy",
            plan_focus=self._neutral_plan_focus(profile),
            revision_requested=revision_requested,
        )
        try:
            query_result = provider.build_coach_evidence_queries(context)
            queries = query_result.evidence_queries
            rationale = query_result.rationale
        except (AttributeError, AiProviderError):
            queries = self._default_evidence_queries(profile.goal or "hypertrophy")
            rationale = ["Fallback interno de consultas cientificas neutras."]
        evidence = evidence_search_service.search_many(queries)
        evidence["query_rationale"] = rationale
        evidence["privacy"] = {
            "personal_data_sent_to_pubmed": False,
            "queries_are_neutral": True,
            "profile_sent_to_pubmed": False,
        }
        return evidence

    def _neutral_plan_focus(self, profile: CoachProfile) -> list[str]:
        focus = [profile.goal or "hypertrophy", "volume", "frequency", "repetitions", "proximity to failure", "rest intervals", "progression", "deload", "protein intake"]
        if profile.experience_level:
            focus.append(f"{profile.experience_level} trainees")
        return focus[:12]

    def _revision_needs_evidence(self, instruction: str) -> bool:
        normalized = instruction.lower()
        markers = ["evidencia", "cient", "estudio", "referencia", "pubmed", "doi", "pmid", "justifica", "por que", "por qué"]
        return any(marker in normalized for marker in markers)

    def _default_evidence_queries(self, goal: str) -> list[str]:
        queries = [
            "resistance training hypertrophy volume systematic review meta analysis",
            "resistance training frequency hypertrophy systematic review",
            "proximity to failure resistance training hypertrophy meta analysis",
            "rest interval resistance training hypertrophy systematic review",
            "protein intake resistance training muscle hypertrophy position stand",
            "resistance training deload fatigue management review",
        ]
        if goal == "strength":
            queries.insert(0, "resistance training strength progression systematic review")
        return queries[:6]

    def _next_action(
        self,
        missing: list[str],
        draft_plans: list[AiTrainingPlan],
        accepted_plan: AiTrainingPlan | None,
        state: dict[str, Any],
    ) -> str:
        if accepted_plan is not None:
            return "train"
        if draft_plans:
            return "review_plan"
        if missing:
            return "continue_interview"
        if state.get("ready_for_plan"):
            return "generate_plan_preview"
        return "continue_interview"

    def _string_list_state(self, state: dict[str, Any], key: str) -> list[str]:
        return self._clean_list(state.get(key) or [])

    def _merge_unique(self, first: list[str], second: list[str]) -> list[str]:
        merged: list[str] = []
        for item in [*first, *second]:
            if item and item not in merged:
                merged.append(item)
        return merged[:30]


class _Skip:
    pass


_SKIP = _Skip()
_PROFILE_FIELDS = {
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
}
_EXTRA_FIELDS = {
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
}


coach_service = CoachService()
