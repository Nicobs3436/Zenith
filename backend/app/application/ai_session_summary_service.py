from collections import defaultdict
from decimal import Decimal
from itertools import pairwise
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.ai_provider import AiSessionSummaryProviderContext, enrich_session_summary_with_provider
from app.infrastructure.db.models.ai import AiSessionSummary
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.workout import WorkoutSession, WorkoutSet
from app.infrastructure.db.repositories.exercises import ExerciseRepository
from app.infrastructure.db.repositories.routines import WorkoutSessionRepository
from app.infrastructure.db.repositories.session_summaries import AiSessionSummaryRepository


class AiSessionSummaryNotFoundError(Exception):
    pass


class AiSessionSummaryCannotGenerateError(Exception):
    pass


class AiSessionSummaryService:
    def get_summary(self, db: Session, session_id: UUID, user: User) -> AiSessionSummary:
        session = WorkoutSessionRepository(db).get_by_user(session_id, user.id)
        if session is None:
            raise AiSessionSummaryNotFoundError
        summary = AiSessionSummaryRepository(db).get_by_session(session_id, user.id)
        if summary is None:
            raise AiSessionSummaryNotFoundError
        return summary

    def generate_summary(self, db: Session, session_id: UUID, user: User) -> AiSessionSummary:
        session = WorkoutSessionRepository(db).get_by_user(session_id, user.id)
        if session is None:
            raise AiSessionSummaryNotFoundError

        input_summary = self._input_summary(db, session, user)
        summary, improvements, drops, warnings, next_recommendation = self._base_text(input_summary)
        provider_result = enrich_session_summary_with_provider(
            AiSessionSummaryProviderContext(
                input_summary=input_summary,
                summary=summary,
                improvements=improvements,
                drops=drops,
                warnings=warnings,
                next_recommendation=next_recommendation,
            )
        )
        input_summary = {
            **input_summary,
            "ai_provider": {
                "provider": provider_result.provider,
                "model": provider_result.model,
                "external_data_sent": provider_result.external_data_sent,
                "fallback_used": provider_result.fallback_used,
            },
        }
        repository = AiSessionSummaryRepository(db)
        saved = repository.upsert(
            user_id=user.id,
            session_id=session.id,
            summary=provider_result.summary,
            improvements=provider_result.improvements,
            drops=provider_result.drops,
            warnings=provider_result.warnings,
            next_recommendation=provider_result.next_recommendation,
            input_summary=input_summary,
            provider=provider_result.provider,
            model=provider_result.model,
            fallback_used=provider_result.fallback_used,
        )
        db.commit()
        return repository.get_by_session(saved.session_id, user.id) or saved

    def _input_summary(self, db: Session, session: WorkoutSession, user: User) -> dict:
        exercises = {exercise.id: exercise for exercise in ExerciseRepository(db).list_accessible(user.id)}
        grouped: dict[UUID, list[WorkoutSet]] = defaultdict(list)
        volume_by_unit: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        rpe_values: list[Decimal] = []
        rir_values: list[int] = []

        for workout_set in session.sets:
            grouped[workout_set.exercise_id].append(workout_set)
            if workout_set.weight_value is not None and workout_set.weight_unit is not None:
                volume_by_unit[workout_set.weight_unit] += workout_set.weight_value * workout_set.reps
            if workout_set.rpe is not None:
                rpe_values.append(workout_set.rpe)
            if workout_set.rir is not None:
                rir_values.append(workout_set.rir)

        exercise_summaries = []
        for exercise_id, sets in grouped.items():
            sorted_sets = sorted(sets, key=lambda item: item.set_number)
            exercise = exercises.get(exercise_id)
            exercise_summaries.append(
                {
                    "exercise_id": str(exercise_id),
                    "exercise_name": exercise.name if exercise else "Ejercicio",
                    "sets": len(sorted_sets),
                    "total_reps": sum(item.reps for item in sorted_sets),
                    "reps_by_set": [item.reps for item in sorted_sets],
                    "weight_units": sorted({item.weight_unit for item in sorted_sets if item.weight_unit}),
                    "max_weight_by_unit": self._max_weight_by_unit(sorted_sets),
                }
            )

        return {
            "privacy": {
                "notes_included": False,
                "email_included": False,
                "username_included": False,
                "tokens_included": False,
            },
            "session": {
                "session_id": str(session.id),
                "routine_id": str(session.routine_id) if session.routine_id else None,
                "started_at": session.started_at.isoformat(),
                "finished_at": session.finished_at.isoformat() if session.finished_at else None,
                "timezone": session.timezone,
            },
            "totals": {
                "sets": len(session.sets),
                "reps": sum(item.reps for item in session.sets),
                "volume_by_unit": {unit: str(value) for unit, value in sorted(volume_by_unit.items())},
                "avg_rpe": self._average_decimal(rpe_values),
                "avg_rir": self._average_int(rir_values),
            },
            "exercises": exercise_summaries,
        }

    def _base_text(self, input_summary: dict) -> tuple[str, list[str], list[str], list[str], str]:
        totals = input_summary["totals"]
        exercises = input_summary["exercises"]
        total_sets = totals["sets"]
        total_reps = totals["reps"]
        exercise_count = len(exercises)
        improvements = []
        drops = []
        warnings = []

        if total_sets == 0:
            warnings.append("La sesion no tiene series registradas.")
            summary = "Sesion registrada sin series; no hay datos suficientes para analizar rendimiento."
            return (
                summary,
                improvements,
                drops,
                warnings,
                "Registra series completas en la proxima sesion para recibir un analisis util.",
            )

        summary = (
            f"Sesion con {total_sets} series, {total_reps} repeticiones y {exercise_count} ejercicios registrados."
        )
        volume_by_unit = totals["volume_by_unit"]
        for unit, volume in volume_by_unit.items():
            improvements.append(f"Volumen registrado en {unit}: {volume}.")
        if not improvements:
            improvements.append(
                "Completaste trabajo sin carga externa registrada; reps y series quedan disponibles para seguimiento."
            )

        for exercise in exercises:
            reps_by_set = exercise["reps_by_set"]
            for previous, current in pairwise(reps_by_set):
                if current < previous:
                    drops.append(f"{exercise['exercise_name']} bajo de {previous} a {current} reps entre series.")
                    break

        if totals["avg_rpe"] is not None and Decimal(str(totals["avg_rpe"])) >= Decimal("9"):
            warnings.append("RPE promedio alto; revisa fatiga antes de subir carga.")
        if totals["avg_rir"] is not None and totals["avg_rir"] <= 1:
            warnings.append("RIR promedio bajo; puede convenir mantener o reducir intensidad.")
        if len(volume_by_unit) > 1:
            warnings.append("Hay cargas en kg y lb; el volumen se mantiene separado por unidad.")

        next_recommendation = "Mantén la progresion y revisa tecnica antes de aumentar carga."
        if warnings:
            next_recommendation = (
                "Prioriza recuperacion y tecnica en la proxima sesion antes de aumentar volumen o carga."
            )
        elif drops:
            next_recommendation = "Mantén la carga y busca reps mas estables entre series antes de progresar."
        return summary, improvements, drops, warnings, next_recommendation

    def _max_weight_by_unit(self, sets: list[WorkoutSet]) -> dict[str, str]:
        max_by_unit: dict[str, Decimal] = {}
        for workout_set in sets:
            if workout_set.weight_value is None or workout_set.weight_unit is None:
                continue
            current = max_by_unit.get(workout_set.weight_unit)
            if current is None or workout_set.weight_value > current:
                max_by_unit[workout_set.weight_unit] = workout_set.weight_value
        return {unit: str(value) for unit, value in sorted(max_by_unit.items())}

    def _average_decimal(self, values: list[Decimal]) -> str | None:
        if not values:
            return None
        return str((sum(values) / len(values)).quantize(Decimal("0.1")))

    def _average_int(self, values: list[int]) -> int | None:
        if not values:
            return None
        return round(sum(values) / len(values))


ai_session_summary_service = AiSessionSummaryService()
