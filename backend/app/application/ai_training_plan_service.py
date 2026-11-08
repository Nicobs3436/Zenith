import re
import unicodedata
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.ai_provider import (
    AiProviderError,
    AiTrainingPlanProviderContext,
    AiTrainingPlanStructureProviderResult,
    build_ai_provider,
)
from app.domain.ai import AiTrainingPlanGenerateRequest, AiTrainingPlanModifyRequest
from app.infrastructure.db.models.ai import AiTrainingPlan
from app.infrastructure.db.models.exercise import Equipment, Exercise, MuscleGroup
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.exercises import ExerciseRepository
from app.infrastructure.db.repositories.routines import RoutineRepository
from app.infrastructure.db.repositories.training_plans import AiTrainingPlanRepository


class AiTrainingPlanNotFoundError(Exception):
    pass


class AiTrainingPlanNotDraftError(Exception):
    pass


class AiTrainingPlanCannotGenerateError(Exception):
    pass


STRUCTURAL_AI_PROVIDERS = {"ollama", "groq"}


class AiTrainingPlanService:
    def generate_plan(
        self,
        db: Session,
        user: User,
        data: AiTrainingPlanGenerateRequest,
        *,
        require_ai_provider: bool = False,
        coach_brief: dict | None = None,
    ) -> AiTrainingPlan:
        data = self._with_normalized_limitations(data)
        exercises = self._exercise_pool(db, user, data.available_equipment)
        if not exercises and not require_ai_provider:
            raise AiTrainingPlanCannotGenerateError("No accessible exercises available.")

        provider_result = self._generate_plan_with_provider(
            data, exercises, require_ai_provider=require_ai_provider, coach_brief=coach_brief
        )
        plan_payload = provider_result.plan_payload
        if coach_brief is not None and plan_payload.get("version") == 3:
            plan_payload["coach_brief"] = coach_brief
        plan_payload = self._resolve_plan_exercises(plan_payload, data, exercises)
        self._validate_plan_payload(plan_payload, data, exercises)
        if plan_payload.get("version") == 3:
            plan_payload["generated_by"] = {**dict(plan_payload.get("generated_by") or {}), "backend_validated": True}
        input_summary = self._input_summary(data, exercises, provider_result)
        if coach_brief and isinstance(coach_brief.get("evidence"), dict):
            input_summary["evidence"] = coach_brief["evidence"]
        plan = AiTrainingPlanRepository(db).create(
            user_id=user.id,
            goal=data.goal,
            level=data.level,
            days_per_week=data.days_per_week,
            session_duration_minutes=data.session_duration_minutes,
            available_equipment=data.available_equipment,
            physical_limitations=data.physical_limitations,
            sensitive_data_acknowledged=data.sensitive_data_acknowledged,
            priorities=data.priorities,
            plan_payload=plan_payload,
            explanation=provider_result.explanation,
            risk_notes=provider_result.risk_notes,
            confidence=provider_result.confidence,
            input_summary=input_summary,
            provider=provider_result.provider,
            model=provider_result.model,
            fallback_used=provider_result.fallback_used,
        )
        db.commit()
        return AiTrainingPlanRepository(db).get_by_user(plan.id, user.id) or plan

    def list_plans(self, db: Session, user: User) -> list[AiTrainingPlan]:
        return AiTrainingPlanRepository(db).list_by_user(user.id)

    def get_plan(self, db: Session, plan_id: UUID, user: User) -> AiTrainingPlan:
        plan = AiTrainingPlanRepository(db).get_by_user(plan_id, user.id)
        if plan is None:
            raise AiTrainingPlanNotFoundError
        return plan

    def accept_plan(self, db: Session, plan_id: UUID, user: User) -> AiTrainingPlan:
        repository = AiTrainingPlanRepository(db)
        plan = repository.get_by_user(plan_id, user.id, for_update=True)
        if plan is None:
            raise AiTrainingPlanNotFoundError
        if plan.status != "draft":
            raise AiTrainingPlanNotDraftError

        routine_repository = RoutineRepository(db)
        exercise_repository = ExerciseRepository(db)
        created_routine_ids: list[str] = []
        created_private_exercise_ids: list[str] = []
        for day in plan.plan_payload.get("routines", []):
            routine = routine_repository.create(
                user_id=user.id,
                name=day["name"],
                description=day.get("description"),
                goal=plan.goal,
            )
            for position, planned in enumerate(day.get("exercises", []), start=1):
                exercise_id_value = planned.get("exercise_id")
                if exercise_id_value:
                    exercise_id = UUID(str(exercise_id_value))
                    if exercise_repository.get_accessible(exercise_id, user.id) is None:
                        raise AiTrainingPlanCannotGenerateError("Plan references an inaccessible exercise.")
                elif planned.get("exercise_source") == "ai_generated_pending":
                    exercise = self._create_private_exercise_from_plan(db, user, planned)
                    exercise_id = exercise.id
                    planned["exercise_id"] = str(exercise_id)
                    planned["exercise_source"] = "ai_generated_private"
                    created_private_exercise_ids.append(str(exercise_id))
                else:
                    raise AiTrainingPlanCannotGenerateError("Plan exercise could not be resolved.")
                routine_repository.add_exercise(
                    routine=routine,
                    exercise_id=exercise_id,
                    position=position,
                    target_sets=planned.get("target_sets"),
                    target_reps_min=planned.get("target_reps_min"),
                    target_reps_max=planned.get("target_reps_max"),
                    target_weight_value=None,
                    target_weight_unit=None,
                    target_rpe=planned.get("target_rpe"),
                    target_rir=planned.get("target_rir"),
                    rest_seconds=planned.get("rest_seconds"),
                    notes=None,
                )
            created_routine_ids.append(str(routine.id))

        plan.status = "accepted"
        plan.reviewed_at = datetime.now(UTC)
        plan.plan_payload = {
            **plan.plan_payload,
            "created_routine_ids": created_routine_ids,
            "created_private_exercise_ids": created_private_exercise_ids,
        }
        db.commit()
        return repository.get_by_user(plan.id, user.id) or plan

    def reject_plan(self, db: Session, plan_id: UUID, user: User) -> AiTrainingPlan:
        repository = AiTrainingPlanRepository(db)
        plan = repository.get_by_user(plan_id, user.id)
        if plan is None:
            raise AiTrainingPlanNotFoundError
        if plan.status != "draft":
            raise AiTrainingPlanNotDraftError
        plan.status = "rejected"
        plan.reviewed_at = datetime.now(UTC)
        db.commit()
        return repository.get_by_user(plan.id, user.id) or plan

    def modify_plan(
        self,
        db: Session,
        plan_id: UUID,
        user: User,
        data: AiTrainingPlanModifyRequest,
        coach_brief: dict | None = None,
    ) -> AiTrainingPlan:
        repository = AiTrainingPlanRepository(db)
        original = repository.get_by_user(plan_id, user.id)
        if original is None:
            raise AiTrainingPlanNotFoundError
        if original.status != "draft":
            raise AiTrainingPlanNotDraftError

        base_request = AiTrainingPlanGenerateRequest(
            goal=original.goal,
            level=original.level,
            days_per_week=original.days_per_week,
            session_duration_minutes=original.session_duration_minutes,
            available_equipment=original.available_equipment,
            physical_limitations=original.physical_limitations,
            sensitive_data_acknowledged=original.sensitive_data_acknowledged or data.sensitive_data_acknowledged,
            priorities=original.priorities,
        )
        modified_request, post_process = self._apply_modification_instruction(base_request, data.instruction)
        modified_request = self._with_normalized_limitations(modified_request)
        exercises = self._exercise_pool(db, user, modified_request.available_equipment)
        if not exercises:
            raise AiTrainingPlanCannotGenerateError("No accessible exercises available.")

        provider_result = self._generate_plan_with_provider(
            modified_request,
            exercises,
            modification_instruction=data.instruction,
            coach_brief=coach_brief,
        )
        plan_payload = provider_result.plan_payload
        plan_payload = self._post_process_plan_payload(plan_payload, post_process)
        self._validate_plan_payload(plan_payload, modified_request, exercises)
        input_summary = self._input_summary(
            modified_request,
            exercises,
            provider_result,
            modified_from_plan_id=str(original.id),
            modification_instruction=data.instruction,
        )
        if coach_brief and isinstance(coach_brief.get("evidence"), dict):
            input_summary["evidence"] = coach_brief["evidence"]
        plan = repository.create(
            user_id=user.id,
            goal=modified_request.goal,
            level=modified_request.level,
            days_per_week=modified_request.days_per_week,
            session_duration_minutes=modified_request.session_duration_minutes,
            available_equipment=modified_request.available_equipment,
            physical_limitations=modified_request.physical_limitations,
            sensitive_data_acknowledged=modified_request.sensitive_data_acknowledged,
            priorities=modified_request.priorities,
            plan_payload=plan_payload,
            explanation=provider_result.explanation,
            risk_notes=provider_result.risk_notes,
            confidence=provider_result.confidence,
            input_summary=input_summary,
            provider=provider_result.provider,
            model=provider_result.model,
            fallback_used=provider_result.fallback_used,
        )
        db.commit()
        return repository.get_by_user(plan.id, user.id) or plan

    def _exercise_pool(self, db: Session, user: User, available_equipment: list[str]) -> list[Exercise]:
        exercises = ExerciseRepository(db).list_accessible(user.id)
        equipment_filter = {item.strip().lower() for item in available_equipment if item.strip()}
        if not equipment_filter:
            return exercises
        filtered = [
            exercise
            for exercise in exercises
            if not exercise.equipment
            or any(equipment.name.lower() in equipment_filter for equipment in exercise.equipment)
        ]
        return filtered or exercises

    def _with_normalized_limitations(self, data: AiTrainingPlanGenerateRequest) -> AiTrainingPlanGenerateRequest:
        limitations = data.physical_limitations.strip() if data.physical_limitations else None
        return data.model_copy(update={"physical_limitations": limitations or None})

    def _input_summary(
        self,
        data: AiTrainingPlanGenerateRequest,
        exercises: list[Exercise],
        provider_result,
        *,
        modified_from_plan_id: str | None = None,
        modification_instruction: str | None = None,
    ) -> dict:
        summary = {
            "privacy": {
                "provider": provider_result.provider,
                "model": provider_result.model,
                "external_data_sent": provider_result.external_data_sent,
                "notes_included": False,
                "physical_limitations_included": bool(data.physical_limitations),
                "sensitive_data_acknowledged": data.sensitive_data_acknowledged,
            },
            "request": {
                "goal": data.goal,
                "level": data.level,
                "days_per_week": data.days_per_week,
                "session_duration_minutes": data.session_duration_minutes,
                "available_equipment": data.available_equipment,
                "priorities": data.priorities,
            },
            "ai_provider": {
                "provider": provider_result.provider,
                "model": provider_result.model,
                "external_data_sent": provider_result.external_data_sent,
                "fallback_used": provider_result.fallback_used,
            },
            "available_exercise_count": len(exercises),
        }
        if modified_from_plan_id is not None:
            summary["modified_from_plan_id"] = modified_from_plan_id
        if modification_instruction is not None:
            summary["modification_instruction"] = modification_instruction
        return summary

    def _generate_plan_with_provider(
        self,
        data: AiTrainingPlanGenerateRequest,
        exercises: list[Exercise],
        *,
        modification_instruction: str | None = None,
        require_ai_provider: bool = False,
        coach_brief: dict | None = None,
    ) -> AiTrainingPlanStructureProviderResult:
        provider = build_ai_provider()
        if require_ai_provider and getattr(provider, "provider", None) not in STRUCTURAL_AI_PROVIDERS:
            raise AiTrainingPlanCannotGenerateError("Coach V3 requires Groq or Ollama as the AI provider.")
        context = self._provider_context(
            data, exercises, modification_instruction=modification_instruction, coach_brief=coach_brief
        )
        if hasattr(provider, "build_training_plan_structure"):
            try:
                result = provider.build_training_plan_structure(context)
                self._validate_plan_payload(result.plan_payload, data, exercises)
                return result
            except (AiProviderError, AiTrainingPlanCannotGenerateError) as error:
                repair_context = self._provider_context(
                    data,
                    exercises,
                    modification_instruction=modification_instruction,
                    validation_errors=[str(error)],
                    coach_brief=coach_brief,
                )
                try:
                    result = provider.build_training_plan_structure(repair_context)
                    self._validate_plan_payload(result.plan_payload, data, exercises)
                    return result
                except (AiProviderError, AiTrainingPlanCannotGenerateError):
                    if require_ai_provider:
                        raise AiTrainingPlanCannotGenerateError(
                            "Ollama could not generate a valid Coach V3 plan."
                        ) from None
                    fallback = self._internal_plan_result(data, exercises, provider=provider, fallback_used=True)
                    self._validate_plan_payload(fallback.plan_payload, data, exercises)
                    return fallback

        if require_ai_provider:
            raise AiTrainingPlanCannotGenerateError(
                "Coach V3 requires an AI provider that can generate plan structure."
            )
        fallback = self._internal_plan_result(data, exercises, provider=provider, fallback_used=False)
        self._validate_plan_payload(fallback.plan_payload, data, exercises)
        return fallback

    def _provider_context(
        self,
        data: AiTrainingPlanGenerateRequest,
        exercises: list[Exercise],
        *,
        modification_instruction: str | None = None,
        validation_errors: list[str] | None = None,
        coach_brief: dict | None = None,
    ) -> AiTrainingPlanProviderContext:
        return AiTrainingPlanProviderContext(
            goal=data.goal,
            level=data.level,
            days_per_week=data.days_per_week,
            session_duration_minutes=data.session_duration_minutes,
            available_equipment=data.available_equipment,
            priorities=data.priorities,
            has_physical_limitations=bool(data.physical_limitations),
            routine_count=data.days_per_week,
            exercises_per_routine=[],
            base_explanation=self._explanation(data),
            base_risk_notes=self._risk_notes(data),
            modification_instruction=modification_instruction,
            exercise_catalog=self._exercise_catalog(exercises),
            physical_limitations=data.physical_limitations if data.sensitive_data_acknowledged else None,
            validation_errors=validation_errors,
            coach_brief=coach_brief,
        )

    def _internal_plan_result(
        self,
        data: AiTrainingPlanGenerateRequest,
        exercises: list[Exercise],
        *,
        provider,
        fallback_used: bool,
    ) -> AiTrainingPlanStructureProviderResult:
        return AiTrainingPlanStructureProviderResult(
            plan_payload=self._build_plan_payload(data, exercises),
            explanation=self._explanation(data),
            risk_notes=self._risk_notes(data),
            confidence="medium",
            provider=getattr(provider, "provider", "internal"),
            model=getattr(provider, "model", "rules"),
            external_data_sent=getattr(provider, "external_data_sent", False),
            fallback_used=fallback_used,
        )

    def _exercise_catalog(self, exercises: list[Exercise]) -> list[dict]:
        return [
            {
                "id": str(exercise.id),
                "name": exercise.name,
                "difficulty": exercise.difficulty,
                "muscle_groups": [muscle.name for muscle in exercise.muscle_groups],
                "equipment": [equipment.name for equipment in exercise.equipment],
            }
            for exercise in exercises[:80]
        ]

    def _validate_plan_payload(
        self,
        plan_payload: dict,
        data: AiTrainingPlanGenerateRequest,
        exercises: list[Exercise],
    ) -> None:
        if plan_payload.get("version") == 3:
            self._validate_plan_payload_v3(plan_payload, data, exercises)
            return

        routines = plan_payload.get("routines")
        if not isinstance(routines, list) or len(routines) != data.days_per_week:
            raise AiTrainingPlanCannotGenerateError("Generated plan routine count is invalid.")

        accessible_exercise_ids = {str(exercise.id) for exercise in exercises}
        for index, routine in enumerate(routines, start=1):
            if not isinstance(routine, dict):
                raise AiTrainingPlanCannotGenerateError("Generated plan routine is invalid.")
            if routine.get("day") != index:
                raise AiTrainingPlanCannotGenerateError("Generated plan routine day is invalid.")
            if not isinstance(routine.get("name"), str) or not routine["name"].strip():
                raise AiTrainingPlanCannotGenerateError("Generated plan routine name is invalid.")
            planned_exercises = routine.get("exercises")
            if not isinstance(planned_exercises, list) or not planned_exercises:
                raise AiTrainingPlanCannotGenerateError("Generated plan exercises are invalid.")
            for planned in planned_exercises:
                self._validate_planned_exercise(planned, accessible_exercise_ids)
        self._validate_plan_quality(routines, data, exercises)

    def _validate_plan_payload_v3(
        self, plan_payload: dict, data: AiTrainingPlanGenerateRequest, exercises: list[Exercise]
    ) -> None:
        required_sections = [
            "generated_by",
            "program_blueprint",
            "coach_rationale",
            "exercise_resolution",
            "weekly_schedule",
            "volume_by_muscle",
            "progression_model",
            "validation_report",
            "acceptance_effects",
        ]
        for section in required_sections:
            if not isinstance(plan_payload.get(section), dict if section not in {"weekly_schedule"} else list):
                raise AiTrainingPlanCannotGenerateError(f"Generated Coach V3 plan is missing {section}.")
        if plan_payload["generated_by"].get("provider") not in STRUCTURAL_AI_PROVIDERS:
            raise AiTrainingPlanCannotGenerateError("Generated Coach V3 plan must be generated by Groq or Ollama.")
        routines = plan_payload.get("routines")
        if not isinstance(routines, list) or len(routines) != data.days_per_week:
            raise AiTrainingPlanCannotGenerateError("Generated plan routine count is invalid.")
        if not plan_payload.get("progression_model"):
            raise AiTrainingPlanCannotGenerateError("Generated plan progression is missing.")
        if not plan_payload.get("volume_by_muscle"):
            raise AiTrainingPlanCannotGenerateError("Generated plan weekly volume is missing.")

        accessible_exercise_ids = {str(exercise.id) for exercise in exercises}
        for index, routine in enumerate(routines, start=1):
            if not isinstance(routine, dict):
                raise AiTrainingPlanCannotGenerateError("Generated plan routine is invalid.")
            if routine.get("day") != index:
                raise AiTrainingPlanCannotGenerateError("Generated plan routine day is invalid.")
            if not isinstance(routine.get("name"), str) or not routine["name"].strip():
                raise AiTrainingPlanCannotGenerateError("Generated plan routine name is invalid.")
            if not isinstance(routine.get("focus"), str) or not routine["focus"].strip():
                raise AiTrainingPlanCannotGenerateError("Generated plan routine focus is invalid.")
            if not isinstance(routine.get("exercises"), list) or not routine["exercises"]:
                raise AiTrainingPlanCannotGenerateError("Generated plan exercises are invalid.")
            for planned in routine["exercises"]:
                self._validate_planned_exercise_v3(planned, accessible_exercise_ids, data)
        self._validate_plan_quality(routines, data, exercises)

    def _validate_planned_exercise_v3(
        self, planned: dict, accessible_exercise_ids: set[str], data: AiTrainingPlanGenerateRequest
    ) -> None:
        if not isinstance(planned, dict):
            raise AiTrainingPlanCannotGenerateError("Generated plan exercise is invalid.")
        source = planned.get("exercise_source") or "ai_generated_pending"
        if source not in {"catalog_matched", "ai_generated_pending", "ai_generated_private"}:
            raise AiTrainingPlanCannotGenerateError("Generated plan exercise source is invalid.")
        exercise_id = planned.get("exercise_id")
        if source == "catalog_matched" and (
            not isinstance(exercise_id, str) or exercise_id not in accessible_exercise_ids
        ):
            raise AiTrainingPlanCannotGenerateError("Generated plan references an inaccessible exercise.")
        if (
            source in {"ai_generated_pending", "ai_generated_private"}
            and exercise_id is not None
            and not isinstance(exercise_id, str)
        ):
            raise AiTrainingPlanCannotGenerateError("Generated plan pending exercise id is invalid.")
        required_strings = [
            "exercise_name",
            "description",
            "technique_notes",
            "difficulty",
            "slot",
            "role",
            "movement_pattern",
            "primary_muscle",
            "reason",
            "progression_hint",
        ]
        for field in required_strings:
            if not isinstance(planned.get(field), str) or not planned[field].strip():
                raise AiTrainingPlanCannotGenerateError(f"Generated plan exercise is missing {field}.")
        if planned["difficulty"] not in {"beginner", "intermediate", "advanced"}:
            raise AiTrainingPlanCannotGenerateError("Generated plan exercise difficulty is invalid.")
        if not isinstance(planned.get("equipment"), list) or not planned["equipment"]:
            raise AiTrainingPlanCannotGenerateError("Generated plan exercise equipment is invalid.")
        if not all(isinstance(item, str) and item.strip() for item in planned["equipment"]):
            raise AiTrainingPlanCannotGenerateError("Generated plan exercise equipment is invalid.")
        if not isinstance(planned.get("secondary_muscles"), list):
            raise AiTrainingPlanCannotGenerateError("Generated plan exercise secondary muscles are invalid.")
        if self._matches_avoided_exercise(planned["exercise_name"], data.priorities):
            raise AiTrainingPlanCannotGenerateError("Generated plan includes an avoided exercise.")
        self._validate_planned_exercise_prescription(planned)

    def _validate_planned_exercise_prescription(self, planned: dict) -> None:
        target_sets = planned.get("target_sets")
        reps_min = planned.get("target_reps_min")
        reps_max = planned.get("target_reps_max")
        rest_seconds = planned.get("rest_seconds")
        target_rir = planned.get("target_rir")
        if not isinstance(target_sets, int) or target_sets < 1 or target_sets > 8:
            raise AiTrainingPlanCannotGenerateError("Generated plan target sets are invalid.")
        if (
            not isinstance(reps_min, int)
            or not isinstance(reps_max, int)
            or reps_min < 1
            or reps_max > 30
            or reps_min > reps_max
        ):
            raise AiTrainingPlanCannotGenerateError("Generated plan target reps are invalid.")
        if not isinstance(rest_seconds, int) or rest_seconds < 45 or rest_seconds > 300:
            raise AiTrainingPlanCannotGenerateError("Generated plan rest is invalid.")
        if target_rir is not None and (not isinstance(target_rir, int) or target_rir < 0 or target_rir > 4):
            raise AiTrainingPlanCannotGenerateError("Generated plan target RIR is invalid.")
        try:
            target_rpe = float(planned.get("target_rpe"))
        except (TypeError, ValueError) as error:
            raise AiTrainingPlanCannotGenerateError("Generated plan target RPE is invalid.") from error
        if target_rpe < 6 or target_rpe > 9:
            raise AiTrainingPlanCannotGenerateError("Generated plan target RPE is invalid.")

    def _validate_plan_quality(
        self, routines: list[dict], data: AiTrainingPlanGenerateRequest, exercises: list[Exercise]
    ) -> None:
        exercise_sets = [
            {
                str(planned.get("exercise_id") or planned.get("exercise_name"))
                for planned in routine.get("exercises", [])
                if isinstance(planned, dict)
            }
            for routine in routines
        ]
        if data.days_per_week > 1 and len(exercises) >= 4 and len({frozenset(item) for item in exercise_sets}) == 1:
            raise AiTrainingPlanCannotGenerateError("Generated plan repeats the same exercises every day.")
        max_exercises = self._max_exercises_per_day(data.session_duration_minutes)
        for routine in routines:
            if len(routine.get("exercises", [])) > max_exercises:
                raise AiTrainingPlanCannotGenerateError("Generated plan has too many exercises for session duration.")

        if data.level == "beginner":
            max_sets_per_day = 16
        elif data.level == "advanced":
            max_sets_per_day = 30
        else:
            max_sets_per_day = 24
        for routine in routines:
            total_sets = sum(
                int(planned.get("target_sets") or 0)
                for planned in routine.get("exercises", [])
                if isinstance(planned, dict)
            )
            if total_sets > max_sets_per_day:
                raise AiTrainingPlanCannotGenerateError("Generated plan volume is too high for level.")

    def _validate_planned_exercise(self, planned: dict, accessible_exercise_ids: set[str]) -> None:
        if not isinstance(planned, dict):
            raise AiTrainingPlanCannotGenerateError("Generated plan exercise is invalid.")
        exercise_id = planned.get("exercise_id")
        if not isinstance(exercise_id, str) or exercise_id not in accessible_exercise_ids:
            raise AiTrainingPlanCannotGenerateError("Generated plan references an inaccessible exercise.")
        target_sets = planned.get("target_sets")
        reps_min = planned.get("target_reps_min")
        reps_max = planned.get("target_reps_max")
        rest_seconds = planned.get("rest_seconds")
        target_rir = planned.get("target_rir")
        if not isinstance(target_sets, int) or target_sets < 1 or target_sets > 10:
            raise AiTrainingPlanCannotGenerateError("Generated plan target sets are invalid.")
        if (
            not isinstance(reps_min, int)
            or not isinstance(reps_max, int)
            or reps_min < 1
            or reps_max > 50
            or reps_min > reps_max
        ):
            raise AiTrainingPlanCannotGenerateError("Generated plan target reps are invalid.")
        if not isinstance(rest_seconds, int) or rest_seconds < 0 or rest_seconds > 600:
            raise AiTrainingPlanCannotGenerateError("Generated plan rest is invalid.")
        if target_rir is not None and (not isinstance(target_rir, int) or target_rir < 0 or target_rir > 10):
            raise AiTrainingPlanCannotGenerateError("Generated plan target RIR is invalid.")
        try:
            target_rpe = float(planned.get("target_rpe"))
        except (TypeError, ValueError) as error:
            raise AiTrainingPlanCannotGenerateError("Generated plan target RPE is invalid.") from error
        if target_rpe < 1 or target_rpe > 10:
            raise AiTrainingPlanCannotGenerateError("Generated plan target RPE is invalid.")

    def _resolve_plan_exercises(
        self, plan_payload: dict, data: AiTrainingPlanGenerateRequest, exercises: list[Exercise]
    ) -> dict:
        if plan_payload.get("version") != 3:
            return plan_payload
        by_name = {self._normalize(exercise.name): exercise for exercise in exercises}
        accessible_ids = {str(exercise.id) for exercise in exercises}
        items = []
        counts = {"catalog_matched_count": 0, "ai_generated_pending_count": 0, "invalid_unresolvable_count": 0}
        routines = []
        for routine in plan_payload.get("routines", []):
            resolved_exercises = []
            for planned in routine.get("exercises", []):
                resolved = dict(planned)
                name = str(resolved.get("exercise_name") or "").strip()
                exercise_id = resolved.get("exercise_id")
                if isinstance(exercise_id, str) and exercise_id in accessible_ids:
                    resolved["exercise_source"] = "catalog_matched"
                    status = "catalog_matched"
                    counts["catalog_matched_count"] += 1
                else:
                    match = by_name.get(self._normalize(name)) if name else None
                    if match is not None:
                        resolved["exercise_id"] = str(match.id)
                        resolved["exercise_source"] = "catalog_matched"
                        status = "catalog_matched"
                        counts["catalog_matched_count"] += 1
                    else:
                        resolved["exercise_id"] = None
                        resolved["exercise_source"] = "ai_generated_pending"
                        status = "ai_generated_pending"
                        counts["ai_generated_pending_count"] += 1
                items.append({"exercise_name": name, "exercise_id": resolved.get("exercise_id"), "status": status})
                resolved_exercises.append(resolved)
            routines.append({**routine, "exercises": resolved_exercises})

        acceptance_effects = dict(plan_payload.get("acceptance_effects") or {})
        acceptance_effects.update(
            {
                "will_create_private_exercises": counts["ai_generated_pending_count"] > 0,
                "private_exercise_count": counts["ai_generated_pending_count"],
                "will_create_routines": True,
                "routine_count": data.days_per_week,
                "requires_user_acceptance": True,
            }
        )
        return {
            **plan_payload,
            "routines": routines,
            "exercise_resolution": {"summary": counts, "items": items},
            "acceptance_effects": acceptance_effects,
        }

    def _create_private_exercise_from_plan(self, db: Session, user: User, planned: dict) -> Exercise:
        muscle_names = [planned["primary_muscle"], *list(planned.get("secondary_muscles") or [])]
        muscles = self._resolve_named_references(db, MuscleGroup, muscle_names)
        equipment = self._resolve_named_references(db, Equipment, list(planned.get("equipment") or []))
        exercise = Exercise(
            name=planned["exercise_name"].strip(),
            description=planned["description"].strip(),
            difficulty=planned["difficulty"].strip(),
            technique_notes=planned["technique_notes"].strip(),
            is_global=False,
            created_by_user_id=user.id,
            muscle_groups=muscles,
            equipment=equipment,
        )
        db.add(exercise)
        db.flush()
        return exercise

    def _resolve_named_references(self, db: Session, model, names: list[str]):
        existing = {self._normalize(item.name): item for item in db.query(model).all()}
        resolved = []
        seen = set()
        for raw_name in names:
            name = str(raw_name).strip()
            normalized = self._normalize(name)
            if not name or normalized in seen:
                continue
            seen.add(normalized)
            item = existing.get(normalized)
            if item is None:
                item = model(name=name)
                db.add(item)
                db.flush()
                existing[normalized] = item
            resolved.append(item)
        return resolved

    def _matches_avoided_exercise(self, exercise_name: str, priorities: list[str]) -> bool:
        name = self._normalize(exercise_name)
        avoided = []
        for priority in priorities:
            normalized = self._normalize(priority)
            if normalized.startswith("evitar "):
                avoided.append(normalized.removeprefix("evitar ").strip())
        return any(item and item in name for item in avoided)

    def _apply_modification_instruction(
        self, data: AiTrainingPlanGenerateRequest, instruction: str
    ) -> tuple[AiTrainingPlanGenerateRequest, dict]:
        normalized = unicodedata.normalize("NFKD", instruction).encode("ascii", "ignore").decode().lower()
        days_per_week = data.days_per_week
        duration = data.session_duration_minutes
        goal = data.goal
        priorities = list(data.priorities)
        post_process: dict = {}

        day_match = re.search(r"\b([1-7])\s*(dias|days)\b", normalized)
        if day_match:
            days_per_week = int(day_match.group(1))
        if "mas corto" in normalized or "menos tiempo" in normalized:
            duration = max(20, duration - 15)
            post_process["max_exercises_per_day"] = 3
        if "menos volumen" in normalized or "menos series" in normalized:
            post_process["sets_delta"] = -1
        if "mas volumen" in normalized or "mas series" in normalized:
            post_process["sets_delta"] = 1
        if "fuerza" in normalized:
            goal = "strength"
        elif "hipertrofia" in normalized:
            goal = "hypertrophy"
        elif "resistencia" in normalized:
            goal = "endurance"
        for priority in ["pecho", "espalda", "pierna", "hombro", "gluteo", "brazos"]:
            if priority in normalized and priority not in priorities:
                priorities.append(priority)

        modified = AiTrainingPlanGenerateRequest(
            goal=goal,
            level=data.level,
            days_per_week=days_per_week,
            session_duration_minutes=duration,
            available_equipment=data.available_equipment,
            physical_limitations=data.physical_limitations,
            sensitive_data_acknowledged=data.sensitive_data_acknowledged,
            priorities=priorities[:10],
        )
        return modified, post_process

    def _post_process_plan_payload(self, plan_payload: dict, post_process: dict) -> dict:
        routines = []
        for routine in plan_payload.get("routines", []):
            exercises = list(routine.get("exercises", []))
            max_exercises = post_process.get("max_exercises_per_day")
            if max_exercises is not None:
                exercises = exercises[:max_exercises]
            sets_delta = post_process.get("sets_delta")
            if sets_delta:
                exercises = [
                    {
                        **exercise,
                        "target_sets": max(1, int(exercise.get("target_sets") or 1) + sets_delta),
                    }
                    for exercise in exercises
                ]
            routines.append({**routine, "exercises": exercises})
        return {**plan_payload, "routines": routines}

    def _build_plan_payload(self, data: AiTrainingPlanGenerateRequest, exercises: list[Exercise]) -> dict:
        routines = []
        exercises_per_day = self._max_exercises_per_day(data.session_duration_minutes)
        used_counts: dict[str, int] = {}
        split = self._split_for(data.days_per_week, data.goal)
        for day_number, focus in enumerate(split, start=1):
            selected = self._select_exercises_for_focus(
                exercises, focus, exercises_per_day, used_counts, data.priorities
            )
            for exercise in selected:
                used_counts[str(exercise.id)] = used_counts.get(str(exercise.id), 0) + 1
            routines.append(
                {
                    "day": day_number,
                    "name": f"{self._focus_label(focus)} Dia {day_number}",
                    "focus": focus,
                    "description": f"Sesion {self._focus_label(focus).lower()} para objetivo {data.goal} y nivel {data.level}.",
                    "exercises": [
                        {
                            "exercise_id": str(exercise.id),
                            "exercise_name": exercise.name,
                            **self._prescription_for(data.goal, data.level, self._exercise_category(exercise)),
                            "reason": f"Seleccionado para cubrir {self._exercise_category(exercise)} dentro de una sesion {self._focus_label(focus).lower()}.",
                        }
                        for exercise in selected
                    ],
                }
            )
        return {
            "version": 2,
            "routines": routines,
            "progression": "Revisa rendimiento y tecnica cada 2-3 sesiones; sube carga solo si completas el rango con RIR suficiente.",
        }

    def _max_exercises_per_day(self, session_duration_minutes: int) -> int:
        if session_duration_minutes < 45:
            return 3
        if session_duration_minutes < 75:
            return 4
        if session_duration_minutes < 105:
            return 5
        return 6

    def _split_for(self, days_per_week: int, goal: str) -> list[str]:
        if days_per_week == 1:
            return ["full_body"]
        if days_per_week == 2:
            return ["full_body_a", "full_body_b"]
        if days_per_week == 3:
            return (
                ["push", "pull", "legs"]
                if goal in {"hypertrophy", "strength"}
                else ["full_body_a", "full_body_b", "full_body_c"]
            )
        if days_per_week == 4:
            return ["upper", "lower", "upper", "lower"]
        if days_per_week == 5:
            return ["push", "pull", "legs", "upper", "lower"]
        if days_per_week == 6:
            return ["push", "pull", "legs", "push", "pull", "legs"]
        return ["push", "pull", "legs", "upper", "lower", "full_body", "recovery"]

    def _select_exercises_for_focus(
        self,
        exercises: list[Exercise],
        focus: str,
        limit: int,
        used_counts: dict[str, int],
        priorities: list[str],
    ) -> list[Exercise]:
        desired = self._desired_categories(focus)
        selected: list[Exercise] = []
        for category in desired:
            candidate = self._best_candidate(exercises, category, selected, used_counts, priorities)
            if candidate is not None:
                selected.append(candidate)
            if len(selected) >= limit:
                return selected

        for exercise in sorted(exercises, key=lambda item: (used_counts.get(str(item.id), 0), item.name)):
            if exercise not in selected:
                selected.append(exercise)
            if len(selected) >= limit:
                break
        return selected

    def _desired_categories(self, focus: str) -> list[str]:
        if focus.startswith("full_body"):
            return ["legs", "push", "pull", "core", "accessory"]
        if focus == "upper":
            return ["push", "pull", "shoulders", "arms", "core"]
        if focus == "lower":
            return ["legs", "hinge", "glutes", "calves", "core"]
        if focus == "push":
            return ["push", "shoulders", "triceps", "push", "core"]
        if focus == "pull":
            return ["pull", "pull", "biceps", "hinge", "core"]
        if focus == "legs":
            return ["legs", "hinge", "glutes", "calves", "core"]
        if focus == "recovery":
            return ["core", "accessory", "pull"]
        return ["push", "pull", "legs", "core"]

    def _best_candidate(
        self,
        exercises: list[Exercise],
        category: str,
        selected: list[Exercise],
        used_counts: dict[str, int],
        priorities: list[str],
    ) -> Exercise | None:
        selected_ids = {exercise.id for exercise in selected}
        candidates = [
            exercise
            for exercise in exercises
            if exercise.id not in selected_ids and self._matches_category(exercise, category)
        ]
        if not candidates:
            return None
        normalized_priorities = [self._normalize(priority) for priority in priorities]
        return sorted(
            candidates,
            key=lambda exercise: (
                used_counts.get(str(exercise.id), 0),
                -self._priority_score(exercise, normalized_priorities),
                exercise.difficulty == "advanced",
                exercise.name,
            ),
        )[0]

    def _matches_category(self, exercise: Exercise, category: str) -> bool:
        exercise_category = self._exercise_category(exercise)
        if category == exercise_category:
            return True
        if category == "accessory" and exercise_category in {"arms", "shoulders", "calves", "core"}:
            return True
        if category == "glutes" and exercise_category in {"legs", "hinge"}:
            return "glute" in self._exercise_text(exercise)
        return False

    def _exercise_category(self, exercise: Exercise) -> str:
        text = self._exercise_text(exercise)
        if any(marker in text for marker in ["core", "abdominal", "oblicuo", "plancha"]):
            return "core"
        if any(marker in text for marker in ["gemelo", "calf"]):
            return "calves"
        if any(marker in text for marker in ["biceps", "triceps", "curl"]):
            return "arms"
        if any(marker in text for marker in ["hombro", "deltoide", "elevacion lateral", "press militar"]):
            return "shoulders"
        if any(
            marker in text for marker in ["peso muerto", "hip thrust", "curl femoral", "isquio", "bisagra", "lumbar"]
        ):
            return "hinge"
        if any(marker in text for marker in ["pierna", "cuadriceps", "sentadilla", "prensa", "zancada", "gluteo"]):
            return "legs"
        if any(marker in text for marker in ["espalda", "dorsal", "remo", "dominada", "jalon"]):
            return "pull"
        if any(marker in text for marker in ["pecho", "press", "flexion", "fondos"]):
            return "push"
        return "accessory"

    def _exercise_text(self, exercise: Exercise) -> str:
        return self._normalize(" ".join([exercise.name, *(muscle.name for muscle in exercise.muscle_groups)]))

    def _priority_score(self, exercise: Exercise, normalized_priorities: list[str]) -> int:
        text = self._exercise_text(exercise)
        return sum(1 for priority in normalized_priorities if priority and priority in text)

    def _focus_label(self, focus: str) -> str:
        labels = {
            "full_body": "Full body",
            "full_body_a": "Full body A",
            "full_body_b": "Full body B",
            "full_body_c": "Full body C",
            "upper": "Tren superior",
            "lower": "Tren inferior",
            "push": "Empuje",
            "pull": "Tiron",
            "legs": "Pierna",
            "recovery": "Recuperacion activa",
        }
        return labels.get(focus, "Sesion")

    def _normalize(self, value: str) -> str:
        return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()

    def _prescription_for(self, goal: str, level: str, category: str = "accessory") -> dict:
        if goal == "strength":
            base = {
                "target_sets": 4,
                "target_reps_min": 3,
                "target_reps_max": 6,
                "rest_seconds": 180,
                "target_rpe": "8",
                "target_rir": 2,
            }
            if category in {"arms", "shoulders", "calves", "core", "accessory"}:
                base = {**base, "target_sets": 3, "target_reps_min": 8, "target_reps_max": 12, "rest_seconds": 90}
        elif goal == "endurance":
            base = {
                "target_sets": 2,
                "target_reps_min": 12,
                "target_reps_max": 20,
                "rest_seconds": 60,
                "target_rpe": "7",
                "target_rir": 3,
            }
        elif goal == "general_health":
            base = {
                "target_sets": 2,
                "target_reps_min": 8,
                "target_reps_max": 15,
                "rest_seconds": 75,
                "target_rpe": "7",
                "target_rir": 3,
            }
        else:
            base = {
                "target_sets": 3,
                "target_reps_min": 8,
                "target_reps_max": 12,
                "rest_seconds": 90,
                "target_rpe": "8",
                "target_rir": 2,
            }
            if category in {"arms", "shoulders", "calves", "core", "accessory"}:
                base = {**base, "target_reps_min": 10, "target_reps_max": 15, "rest_seconds": 75}
        if level == "beginner":
            base = {**base, "target_sets": max(2, base["target_sets"] - 1)}
        if level == "advanced":
            base = {**base, "target_sets": base["target_sets"] + 1}
        return base

    def _explanation(self, data: AiTrainingPlanGenerateRequest) -> str:
        return f"Plan adaptativo de {data.days_per_week} dias para objetivo {data.goal}, nivel {data.level} y sesiones de {data.session_duration_minutes} minutos."

    def _risk_notes(self, data: AiTrainingPlanGenerateRequest) -> str | None:
        if data.physical_limitations:
            return "Has indicado limitaciones fisicas. Este plan no sustituye consejo medico; evita ejercicios que causen dolor y consulta a un profesional si hay dudas."
        return "Si aparece dolor, mareo o perdida clara de tecnica, detén la sesion y ajusta la carga."


ai_training_plan_service = AiTrainingPlanService()
