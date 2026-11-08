from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.ai_provider import AiProviderContext, enrich_with_provider
from app.infrastructure.db.models.ai import AiSuggestion
from app.infrastructure.db.models.exercise import Exercise
from app.infrastructure.db.models.routine import Routine, RoutineExercise
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.workout import WorkoutSession, WorkoutSet
from app.infrastructure.db.repositories.ai_suggestions import AiSuggestionRepository
from app.infrastructure.db.repositories.exercises import ExerciseRepository
from app.infrastructure.db.repositories.routines import RoutineRepository
from app.infrastructure.db.repositories.stats import StatsRepository

TWO_PLACES = Decimal("0.01")


class AiSuggestionNotFoundError(Exception):
    pass


class AiSuggestionNotPendingError(Exception):
    pass


class AiSuggestionCannotApplyError(Exception):
    pass


class AiRoutineAnalysisNotFoundError(Exception):
    pass


@dataclass
class SessionPerformance:
    session: WorkoutSession
    sets: list[WorkoutSet]

    @property
    def weighted_sets(self) -> list[WorkoutSet]:
        return [workout_set for workout_set in self.sets if workout_set.weight_value is not None]

    @property
    def unit(self) -> str | None:
        units = {workout_set.weight_unit for workout_set in self.weighted_sets}
        return units.pop() if len(units) == 1 else None

    @property
    def max_weight(self) -> Decimal | None:
        weights = [Decimal(workout_set.weight_value) for workout_set in self.weighted_sets]
        return max(weights) if weights else None

    @property
    def avg_reps(self) -> Decimal:
        return Decimal(sum(workout_set.reps for workout_set in self.sets)) / Decimal(len(self.sets))

    @property
    def avg_rpe(self) -> Decimal | None:
        values = [Decimal(workout_set.rpe) for workout_set in self.sets if workout_set.rpe is not None]
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else None

    @property
    def avg_rir(self) -> Decimal | None:
        values = [Decimal(workout_set.rir) for workout_set in self.sets if workout_set.rir is not None]
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else None

    @property
    def total_volume(self) -> Decimal | None:
        if self.unit is None:
            return None
        weighted_sets = self.weighted_sets
        if not weighted_sets:
            return None
        return sum(Decimal(workout_set.weight_value) * workout_set.reps for workout_set in weighted_sets)

    @property
    def rep_drop(self) -> int:
        return self.sets[0].reps - self.sets[-1].reps if self.sets else 0


class AiCoachService:
    def generate_suggestions(self, db: Session, user: User) -> list[AiSuggestion]:
        repository = AiSuggestionRepository(db)
        suggestion_ids: list[UUID] = []
        for routine in RoutineRepository(db).list_by_user(user.id):
            for routine_exercise in routine.exercises:
                suggestion = self._build_suggestion(db, user, routine, routine_exercise)
                if suggestion is None:
                    repository.expire_pending_except(
                        user_id=user.id,
                        routine_exercise_id=routine_exercise.id,
                        keep_suggestion_id=None,
                    )
                    continue

                matching = repository.find_matching_pending(
                    user_id=user.id,
                    routine_exercise_id=routine_exercise.id,
                    suggestion_type=suggestion["suggestion_type"],
                    apply_payload=suggestion["apply_payload"],
                )
                if matching is None:
                    matching = repository.create(**suggestion)

                repository.expire_pending_except(
                    user_id=user.id,
                    routine_exercise_id=routine_exercise.id,
                    keep_suggestion_id=matching.id,
                )
                suggestion_ids.append(matching.id)

        db.commit()
        return [suggestion for suggestion_id in suggestion_ids if (suggestion := repository.get_by_user(suggestion_id, user.id))]

    def list_suggestions(self, db: Session, user: User) -> list[AiSuggestion]:
        return AiSuggestionRepository(db).list_by_user(user.id)

    def analyze_routine_goal(self, db: Session, routine_id: UUID, user: User) -> list[AiSuggestion]:
        routine = RoutineRepository(db).get_by_user(routine_id, user.id)
        if routine is None:
            raise AiRoutineAnalysisNotFoundError
        goal = self._normalized_goal(routine.goal)
        repository = AiSuggestionRepository(db)
        suggestion_ids: list[UUID] = []
        for routine_exercise in routine.exercises:
            suggestion = self._build_routine_goal_suggestion(user, routine, routine_exercise, goal)
            if suggestion is None:
                repository.expire_pending_by_type_except(
                    user_id=user.id,
                    routine_exercise_id=routine_exercise.id,
                    suggestion_type="routine_goal_adjustment",
                    keep_suggestion_id=None,
                )
                continue
            matching = repository.find_matching_pending(
                user_id=user.id,
                routine_exercise_id=routine_exercise.id,
                suggestion_type=suggestion["suggestion_type"],
                apply_payload=suggestion["apply_payload"],
            )
            if matching is None:
                matching = repository.create(**suggestion)
            repository.expire_pending_by_type_except(
                user_id=user.id,
                routine_exercise_id=routine_exercise.id,
                suggestion_type="routine_goal_adjustment",
                keep_suggestion_id=matching.id,
            )
            suggestion_ids.append(matching.id)

        repository.expire_pending_by_routine_type_except(
            user_id=user.id,
            routine_id=routine.id,
            suggestion_type="routine_goal_adjustment",
            keep_suggestion_ids=set(suggestion_ids),
        )

        db.commit()
        return [suggestion for suggestion_id in suggestion_ids if (suggestion := repository.get_by_user(suggestion_id, user.id))]

    def accept_suggestion(self, db: Session, suggestion_id: UUID, user: User) -> AiSuggestion:
        repository = AiSuggestionRepository(db)
        suggestion = repository.get_by_user(suggestion_id, user.id, for_update=True)
        if suggestion is None:
            raise AiSuggestionNotFoundError
        if suggestion.status != "pending":
            raise AiSuggestionNotPendingError

        payload = suggestion.apply_payload
        routine_exercise_id = payload.get("routine_exercise_id")
        changes = payload.get("changes")
        if not routine_exercise_id or not isinstance(changes, dict):
            raise AiSuggestionCannotApplyError

        target = repository.get_routine_exercise_for_user(UUID(str(routine_exercise_id)), user.id)
        if target is None:
            raise AiSuggestionCannotApplyError
        _routine, routine_exercise = target
        self._apply_changes(db, user, routine_exercise, changes)

        now = datetime.now(UTC)
        suggestion.status = "accepted"
        suggestion.reviewed_at = now
        suggestion.applied_at = now
        db.commit()
        loaded = repository.get_by_user(suggestion_id, user.id)
        return loaded or suggestion

    def reject_suggestion(self, db: Session, suggestion_id: UUID, user: User) -> AiSuggestion:
        repository = AiSuggestionRepository(db)
        suggestion = repository.get_by_user(suggestion_id, user.id)
        if suggestion is None:
            raise AiSuggestionNotFoundError
        if suggestion.status != "pending":
            raise AiSuggestionNotPendingError
        suggestion.status = "rejected"
        suggestion.reviewed_at = datetime.now(UTC)
        db.commit()
        loaded = repository.get_by_user(suggestion_id, user.id)
        return loaded or suggestion

    def _build_suggestion(
        self, db: Session, user: User, routine: Routine, routine_exercise: RoutineExercise
    ) -> dict | None:
        performances = self._performances_for_exercise(db, user.id, routine_exercise.exercise_id)
        if len(performances) < 2:
            return None

        latest = performances[-1]
        previous = performances[-2]
        if latest.unit is None or previous.unit != latest.unit:
            return None

        input_summary = self._input_summary(routine, routine_exercise, performances[-3:])
        target_reps_max = routine_exercise.target_reps_max or max(workout_set.reps for workout_set in latest.sets)

        deload_changes = self._suggest_deload(performances[-3:], routine_exercise)
        if deload_changes is not None:
            return self._suggestion_payload(
                user=user,
                routine=routine,
                routine_exercise=routine_exercise,
                suggestion_type="deload_recommended",
                input_summary=input_summary,
                recommendation="Aplica una descarga conservadora en este ejercicio.",
                explanation="Hay senales repetidas de fatiga. Un deload temporal puede ayudar a recuperar rendimiento sin borrar el ejercicio del plan.",
                changes=deload_changes,
                rule_triggered="repeated_fatigue_deload",
            )

        swap = self._suggest_exercise_swap(db, user, performances[-3:], routine_exercise)
        if swap is not None:
            return self._suggestion_payload(
                user=user,
                routine=routine,
                routine_exercise=routine_exercise,
                suggestion_type="exercise_swap",
                input_summary=input_summary,
                recommendation=f"Cambia a {swap['exercise_name']} en este bloque.",
                explanation="El ejercicio actual muestra baja tolerancia reciente. Una alternativa compatible puede mantener el estimulo sin forzar el mismo patron.",
                changes={"exercise_id": swap["exercise_id"]},
                rule_triggered="poor_tolerance_exercise_swap",
                planned_change_extra={"exercise_name": swap["exercise_name"], "reason": swap["reason"]},
            )

        if self._should_reduce_volume(latest, routine_exercise):
            target_sets = max(1, (routine_exercise.target_sets or len(latest.sets)) - 1)
            return self._suggestion_payload(
                user=user,
                routine=routine,
                routine_exercise=routine_exercise,
                suggestion_type="reduce_volume",
                input_summary=input_summary,
                recommendation=f"Baja a {target_sets} series en este ejercicio.",
                explanation="El esfuerzo reciente fue alto. Reducir una serie ayuda a recuperar sin borrar el ejercicio del plan.",
                changes={"target_sets": target_sets},
                rule_triggered="high_effort_reduce_volume",
            )

        rest_seconds = self._suggest_rest(latest, routine_exercise)
        if rest_seconds is not None:
            return self._suggestion_payload(
                user=user,
                routine=routine,
                routine_exercise=routine_exercise,
                suggestion_type="increase_rest",
                input_summary=input_summary,
                recommendation=f"Sube el descanso a {rest_seconds} segundos.",
                explanation="Hay una caida clara de repeticiones entre la primera y la ultima serie. Mas descanso puede estabilizar el rendimiento.",
                changes={"rest_seconds": rest_seconds},
                rule_triggered="large_rep_drop_between_sets",
            )

        if self._is_plateau(performances[-3:]):
            new_min = (routine_exercise.target_reps_min or target_reps_max) + 1
            new_max = target_reps_max + 1
            return self._suggestion_payload(
                user=user,
                routine=routine,
                routine_exercise=routine_exercise,
                suggestion_type="plateau_detected",
                input_summary=input_summary,
                recommendation=f"Prueba un rango de {new_min}-{new_max} reps antes de volver a subir carga.",
                explanation="El rendimiento se mantuvo plano durante varias sesiones. Cambiar ligeramente el objetivo de reps puede desbloquear progreso.",
                changes={"target_reps_min": new_min, "target_reps_max": new_max},
                rule_triggered="plateau_same_weight_and_reps",
            )

        change_reps = self._suggest_change_reps(latest, routine_exercise)
        if change_reps is not None:
            return self._suggestion_payload(
                user=user,
                routine=routine,
                routine_exercise=routine_exercise,
                suggestion_type="change_reps",
                input_summary=input_summary,
                recommendation=f"Ajusta el objetivo a {change_reps['target_reps_min']}-{change_reps['target_reps_max']} reps.",
                explanation="No estas llegando al rango actual, pero el esfuerzo no parece extremo. Un rango mas realista permite progresar sin forzar volumen inutil.",
                changes=change_reps,
                rule_triggered="below_rep_target_without_extreme_fatigue",
            )

        if self._should_increase_weight(latest, previous, target_reps_max):
            next_weight = self._next_weight(latest.max_weight)
            return self._suggestion_payload(
                user=user,
                routine=routine,
                routine_exercise=routine_exercise,
                suggestion_type="increase_weight",
                input_summary=input_summary,
                recommendation=f"Sube el peso objetivo a {next_weight} {latest.unit}.",
                explanation="Completaste el rango alto de repeticiones en sesiones recientes con margen razonable. La sobrecarga es conservadora.",
                changes={"target_weight_value": str(next_weight), "target_weight_unit": latest.unit},
                rule_triggered="rep_target_met_with_recovery_margin",
            )

        return None

    def _build_routine_goal_suggestion(
        self,
        user: User,
        routine: Routine,
        routine_exercise: RoutineExercise,
        goal: str | None,
    ) -> dict | None:
        if goal is None:
            return None
        changes = self._routine_goal_changes(goal, routine_exercise)
        if not changes:
            return None
        input_summary = self._routine_goal_input_summary(routine, routine_exercise, goal)
        return self._suggestion_payload(
            user=user,
            routine=routine,
            routine_exercise=routine_exercise,
            suggestion_type="routine_goal_adjustment",
            input_summary=input_summary,
            recommendation=self._routine_goal_recommendation(goal, changes),
            explanation=f"Los objetivos planificados no estan alineados con una rutina de {goal}.",
            changes=changes,
            rule_triggered=f"routine_goal_{goal}_alignment",
        )

    def _normalized_goal(self, goal: str | None) -> str | None:
        if not goal:
            return None
        normalized = goal.strip().lower()
        if any(value in normalized for value in ["strength", "fuerza"]):
            return "strength"
        if any(value in normalized for value in ["hypertrophy", "hipertrofia", "hipertrofía"]):
            return "hypertrophy"
        if any(value in normalized for value in ["endurance", "resistencia"]):
            return "endurance"
        if any(value in normalized for value in ["health", "salud", "general"]):
            return "general_health"
        return None

    def _routine_goal_changes(self, goal: str, routine_exercise: RoutineExercise) -> dict:
        changes: dict = {}
        if goal == "strength":
            if routine_exercise.target_reps_max is None or routine_exercise.target_reps_max > 6:
                changes.update({"target_reps_min": 3, "target_reps_max": 6})
            if routine_exercise.rest_seconds is None or routine_exercise.rest_seconds < 150:
                changes["rest_seconds"] = 180
            if routine_exercise.target_sets is None or routine_exercise.target_sets < 3:
                changes["target_sets"] = 3
        elif goal == "hypertrophy":
            if (
                routine_exercise.target_reps_min is None
                or routine_exercise.target_reps_max is None
                or routine_exercise.target_reps_min < 8
                or routine_exercise.target_reps_max > 12
            ):
                changes.update({"target_reps_min": 8, "target_reps_max": 12})
            if routine_exercise.target_sets is None or routine_exercise.target_sets < 3:
                changes["target_sets"] = 3
            if routine_exercise.rest_seconds is not None and routine_exercise.rest_seconds > 150:
                changes["rest_seconds"] = 90
        elif goal == "endurance":
            if routine_exercise.target_reps_max is None or routine_exercise.target_reps_max < 15:
                changes.update({"target_reps_min": 12, "target_reps_max": 20})
            if routine_exercise.rest_seconds is not None and routine_exercise.rest_seconds > 90:
                changes["rest_seconds"] = 60
            if routine_exercise.target_sets is not None and routine_exercise.target_sets > 3:
                changes["target_sets"] = 3
        elif goal == "general_health":
            if (
                routine_exercise.target_reps_min is None
                or routine_exercise.target_reps_max is None
                or routine_exercise.target_reps_min < 8
                or routine_exercise.target_reps_max > 12
            ):
                changes.update({"target_reps_min": 8, "target_reps_max": 12})
            if routine_exercise.target_sets is None or routine_exercise.target_sets < 2 or routine_exercise.target_sets > 3:
                changes["target_sets"] = 3
            if routine_exercise.rest_seconds is None or routine_exercise.rest_seconds > 120:
                changes["rest_seconds"] = 90
        return changes

    def _routine_goal_input_summary(self, routine: Routine, routine_exercise: RoutineExercise, goal: str) -> dict:
        return {
            "privacy": {
                "provider": "internal_local_rules",
                "external_data_sent": False,
                "notes_included": False,
            },
            "routine": {
                "id": str(routine.id),
                "name": routine.name,
                "goal": routine.goal,
                "normalized_goal": goal,
            },
            "planned_exercise": {
                "id": str(routine_exercise.id),
                "exercise_id": str(routine_exercise.exercise_id),
                "target_sets": routine_exercise.target_sets,
                "target_reps_min": routine_exercise.target_reps_min,
                "target_reps_max": routine_exercise.target_reps_max,
                "rest_seconds": routine_exercise.rest_seconds,
            },
            "analysis_window": {"sessions_used": 0},
            "metrics": {"source": "routine_goal"},
        }

    def _routine_goal_recommendation(self, goal: str, changes: dict) -> str:
        if goal == "strength":
            return "Ajusta reps bajas, series suficientes y descanso largo para fuerza."
        if goal == "hypertrophy":
            return "Ajusta el ejercicio a un rango moderado de hipertrofia."
        if goal == "endurance":
            return "Ajusta el ejercicio a reps altas y descansos mas cortos para resistencia."
        return "Ajusta el ejercicio a parametros conservadores de salud general."

    def _performances_for_exercise(self, db: Session, user_id: UUID, exercise_id: UUID) -> list[SessionPerformance]:
        rows = StatsRepository(db).list_workout_sets(user_id=user_id, exercise_id=exercise_id)
        grouped: dict[UUID, tuple[WorkoutSession, list[WorkoutSet]]] = {}
        for workout_set, session, _exercise in rows:
            if session.id not in grouped:
                grouped[session.id] = (session, [])
            grouped[session.id][1].append(workout_set)
        return [SessionPerformance(session=session, sets=sets) for session, sets in sorted(grouped.values(), key=lambda item: item[0].started_at)]

    def _input_summary(
        self, routine: Routine, routine_exercise: RoutineExercise, performances: list[SessionPerformance]
    ) -> dict:
        return {
            "privacy": {
                "provider": "internal_local_rules",
                "external_data_sent": False,
                "notes_included": False,
            },
            "routine": {
                "id": str(routine.id),
                "name": routine.name,
                "goal": routine.goal,
            },
            "planned_exercise": {
                "id": str(routine_exercise.id),
                "exercise_id": str(routine_exercise.exercise_id),
                "target_sets": routine_exercise.target_sets,
                "target_reps_min": routine_exercise.target_reps_min,
                "target_reps_max": routine_exercise.target_reps_max,
                "target_weight_value": str(routine_exercise.target_weight_value) if routine_exercise.target_weight_value is not None else None,
                "target_weight_unit": routine_exercise.target_weight_unit,
                "target_rpe": str(routine_exercise.target_rpe) if routine_exercise.target_rpe is not None else None,
                "target_rir": routine_exercise.target_rir,
                "rest_seconds": routine_exercise.rest_seconds,
            },
            "recent_sessions": [
                {
                    "session_id": str(performance.session.id),
                    "started_at": performance.session.started_at.isoformat(),
                    "sets": [
                        {
                            "set_number": workout_set.set_number,
                            "reps": workout_set.reps,
                            "weight_value": str(workout_set.weight_value) if workout_set.weight_value is not None else None,
                            "weight_unit": workout_set.weight_unit,
                            "rpe": str(workout_set.rpe) if workout_set.rpe is not None else None,
                            "rir": workout_set.rir,
                            "rest_seconds": workout_set.rest_seconds,
                        }
                        for workout_set in performance.sets
                    ],
                }
                for performance in performances
            ],
            "analysis_window": {
                "sessions_used": len(performances),
            },
            "metrics": self._metrics(performances),
        }

    def _metrics(self, performances: list[SessionPerformance]) -> dict:
        latest = performances[-1]
        return {
            "avg_reps": str(latest.avg_reps.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)),
            "max_weight": str(latest.max_weight) if latest.max_weight is not None else None,
            "weight_unit": latest.unit,
            "avg_rpe": str(latest.avg_rpe.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)) if latest.avg_rpe is not None else None,
            "avg_rir": str(latest.avg_rir.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)) if latest.avg_rir is not None else None,
            "rep_drop": latest.sets[0].reps - latest.sets[-1].reps if latest.sets else 0,
            "total_volume": str(latest.total_volume) if latest.total_volume is not None else None,
        }

    def _suggestion_payload(
        self,
        *,
        user: User,
        routine: Routine,
        routine_exercise: RoutineExercise,
        suggestion_type: str,
        input_summary: dict,
        recommendation: str,
        explanation: str,
        changes: dict,
        rule_triggered: str,
        planned_change_extra: dict | None = None,
    ) -> dict:
        input_summary = {
            **input_summary,
            "rule_triggered": rule_triggered,
            "planned_change": {**changes, **(planned_change_extra or {})},
        }
        apply_payload = {"routine_exercise_id": str(routine_exercise.id), "changes": changes}
        provider_result = enrich_with_provider(
            AiProviderContext(
                suggestion_type=suggestion_type,
                input_summary=input_summary,
                recommendation=recommendation,
                explanation=explanation,
                apply_payload=apply_payload,
            )
        )
        input_summary = {
            **input_summary,
            "privacy": {
                **input_summary.get("privacy", {}),
                "provider": provider_result.provider,
                "model": provider_result.model,
                "external_data_sent": provider_result.external_data_sent,
            },
            "ai_provider": {
                "provider": provider_result.provider,
                "model": provider_result.model,
                "external_data_sent": provider_result.external_data_sent,
                "fallback_used": provider_result.fallback_used,
                "prompt_summary": {
                    "included_notes": False,
                    "included_account_data": False,
                    "included_metrics": True,
                    "included_planned_change": True,
                },
            },
        }
        return {
            "user_id": user.id,
            "routine_id": routine.id,
            "routine_exercise_id": routine_exercise.id,
            "exercise_id": routine_exercise.exercise_id,
            "suggestion_type": suggestion_type,
            "input_summary": input_summary,
            "recommendation": provider_result.recommendation,
            "explanation": provider_result.explanation,
            "risk_notes": provider_result.risk_notes,
            "confidence": provider_result.confidence,
            "apply_payload": apply_payload,
        }

    def _should_reduce_volume(self, latest: SessionPerformance, routine_exercise: RoutineExercise) -> bool:
        if (routine_exercise.target_sets or len(latest.sets)) <= 1:
            return False
        return (latest.avg_rpe is not None and latest.avg_rpe >= Decimal("9")) or (
            latest.avg_rir is not None and latest.avg_rir <= Decimal("0.5")
        )

    def _suggest_deload(self, performances: list[SessionPerformance], routine_exercise: RoutineExercise) -> dict | None:
        if len(performances) < 3:
            return None
        latest = performances[-1]
        previous = performances[-2]
        if any(performance.unit != latest.unit for performance in performances):
            return None
        high_rpe_sessions = sum(
            1 for performance in performances if performance.avg_rpe is not None and performance.avg_rpe >= Decimal("9")
        )
        low_rir_sessions = sum(
            1 for performance in performances if performance.avg_rir is not None and performance.avg_rir <= Decimal("1")
        )
        volume_drop = (
            latest.total_volume is not None
            and previous.total_volume is not None
            and latest.total_volume < previous.total_volume
        )
        signals = [high_rpe_sessions >= 2, low_rir_sessions >= 2, latest.rep_drop >= 3, volume_drop]
        if sum(1 for signal in signals if signal) < 2:
            return None

        changes: dict = {}
        current_sets = routine_exercise.target_sets or len(latest.sets)
        if current_sets > 1:
            changes["target_sets"] = current_sets - 1

        current_weight = routine_exercise.target_weight_value or latest.max_weight
        current_unit = routine_exercise.target_weight_unit or latest.unit
        if current_weight is not None and current_weight > 0 and current_unit in {"kg", "lb"}:
            changes["target_weight_value"] = str((Decimal(current_weight) * Decimal("0.90")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP))
            changes["target_weight_unit"] = current_unit

        if latest.rep_drop >= 3:
            changes["rest_seconds"] = min((routine_exercise.rest_seconds or 90) + 30, 300)

        return changes or None

    def _suggest_exercise_swap(
        self,
        db: Session,
        user: User,
        performances: list[SessionPerformance],
        routine_exercise: RoutineExercise,
    ) -> dict | None:
        if len(performances) < 2 or routine_exercise.target_reps_min is None:
            return None
        latest = performances[-1]
        previous = performances[-2]
        target_min = Decimal(routine_exercise.target_reps_min)
        below_target_repeated = latest.avg_reps < target_min and previous.avg_reps < target_min
        poor_tolerance = (
            (latest.avg_rpe is not None and latest.avg_rpe >= Decimal("8.5"))
            or (latest.avg_rir is not None and latest.avg_rir <= Decimal("1"))
            or latest.rep_drop >= 3
        )
        if not below_target_repeated or not poor_tolerance:
            return None

        current = ExerciseRepository(db).get_accessible(routine_exercise.exercise_id, user.id)
        if current is None:
            return None
        candidates = [
            exercise
            for exercise in ExerciseRepository(db).list_accessible(user.id)
            if exercise.id != current.id and self._exercise_swap_score(current, exercise) > 0
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda exercise: (-self._exercise_swap_score(current, exercise), exercise.name.lower()))
        selected = candidates[0]
        return {
            "exercise_id": str(selected.id),
            "exercise_name": selected.name,
            "reason": "same_muscle_equipment_compatible",
        }

    def _exercise_swap_score(self, current: Exercise, candidate: Exercise) -> int:
        current_muscles = {muscle.id for muscle in current.muscle_groups}
        candidate_muscles = {muscle.id for muscle in candidate.muscle_groups}
        current_equipment = {equipment.id for equipment in current.equipment}
        candidate_equipment = {equipment.id for equipment in candidate.equipment}
        score = 0
        if current_muscles and current_muscles.intersection(candidate_muscles):
            score += 3
        if not current_equipment or current_equipment.intersection(candidate_equipment):
            score += 2
        if current.difficulty and candidate.difficulty == current.difficulty:
            score += 1
        return score

    def _suggest_rest(self, latest: SessionPerformance, routine_exercise: RoutineExercise) -> int | None:
        if len(latest.sets) < 2:
            return None
        first_reps = latest.sets[0].reps
        last_reps = latest.sets[-1].reps
        if first_reps - last_reps < 3:
            return None
        return min((routine_exercise.rest_seconds or 90) + 30, 300)

    def _suggest_change_reps(self, latest: SessionPerformance, routine_exercise: RoutineExercise) -> dict | None:
        if routine_exercise.target_reps_min is None or latest.avg_reps >= Decimal(routine_exercise.target_reps_min):
            return None
        if latest.avg_rpe is not None and latest.avg_rpe > Decimal("8.5"):
            return None
        if latest.avg_rir is not None and latest.avg_rir < Decimal("1"):
            return None

        latest_avg_reps = max(0, int(latest.avg_reps))
        new_min = max(0, latest_avg_reps - 1)
        new_max = max(new_min, latest_avg_reps + 1)
        return {"target_reps_min": new_min, "target_reps_max": new_max}

    def _should_increase_weight(self, latest: SessionPerformance, previous: SessionPerformance, target_reps_max: int) -> bool:
        if latest.max_weight is None or previous.max_weight is None:
            return False
        if latest.max_weight < previous.max_weight:
            return False
        if latest.avg_reps < Decimal(target_reps_max) or previous.avg_reps < Decimal(target_reps_max):
            return False
        if latest.avg_rpe is not None and latest.avg_rpe > Decimal("8.5"):
            return False
        if latest.avg_rir is not None and latest.avg_rir < Decimal("1"):
            return False
        return True

    def _next_weight(self, current: Decimal | None) -> Decimal:
        if current is None:
            return Decimal("0.00")
        return (current * Decimal("1.025")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    def _is_plateau(self, performances: list[SessionPerformance]) -> bool:
        if len(performances) < 3:
            return False
        max_weights = [performance.max_weight for performance in performances]
        avg_reps = [performance.avg_reps.quantize(TWO_PLACES, rounding=ROUND_HALF_UP) for performance in performances]
        return len(set(max_weights)) == 1 and len(set(avg_reps)) == 1

    def _apply_changes(self, db: Session, user: User, routine_exercise: RoutineExercise, changes: dict) -> None:
        allowed = {"target_weight_value", "target_weight_unit", "target_sets", "target_reps_min", "target_reps_max", "rest_seconds", "exercise_id"}
        if not set(changes).issubset(allowed):
            raise AiSuggestionCannotApplyError
        self._validate_changes(db, user, routine_exercise, changes)
        for field, value in changes.items():
            if field == "target_weight_value" and value is not None:
                setattr(routine_exercise, field, Decimal(str(value)))
            elif field == "exercise_id":
                setattr(routine_exercise, field, UUID(str(value)))
            else:
                setattr(routine_exercise, field, value)

    def _validate_changes(self, db: Session, user: User, routine_exercise: RoutineExercise, changes: dict) -> None:
        if "target_sets" in changes and (not isinstance(changes["target_sets"], int) or changes["target_sets"] < 1):
            raise AiSuggestionCannotApplyError
        if "rest_seconds" in changes and (not isinstance(changes["rest_seconds"], int) or changes["rest_seconds"] < 0):
            raise AiSuggestionCannotApplyError
        if "target_weight_unit" in changes and changes["target_weight_unit"] not in {"kg", "lb", None}:
            raise AiSuggestionCannotApplyError
        if "target_weight_value" in changes and changes["target_weight_value"] is not None:
            try:
                if Decimal(str(changes["target_weight_value"])) < 0:
                    raise AiSuggestionCannotApplyError
            except Exception as error:
                raise AiSuggestionCannotApplyError from error
        if ("target_weight_value" in changes) != ("target_weight_unit" in changes):
            raise AiSuggestionCannotApplyError
        reps_min = changes.get("target_reps_min", routine_exercise.target_reps_min)
        reps_max = changes.get("target_reps_max", routine_exercise.target_reps_max)
        for value in [reps_min, reps_max]:
            if value is not None and (not isinstance(value, int) or value < 0):
                raise AiSuggestionCannotApplyError
        if reps_min is not None and reps_max is not None and reps_min > reps_max:
            raise AiSuggestionCannotApplyError
        if "exercise_id" in changes:
            try:
                exercise_id = UUID(str(changes["exercise_id"]))
            except (TypeError, ValueError) as error:
                raise AiSuggestionCannotApplyError from error
            if exercise_id == routine_exercise.exercise_id or ExerciseRepository(db).get_accessible(exercise_id, user.id) is None:
                raise AiSuggestionCannotApplyError


ai_coach_service = AiCoachService()
