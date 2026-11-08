"""Exportacion y eliminacion de cuenta (derechos de acceso y supresion de datos del usuario)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.ai import (
    AiCoachIntake,
    AiSessionSummary,
    AiSuggestion,
    AiTrainingPlan,
    CoachConversation,
    CoachMemoryEvent,
    CoachPlannedSession,
    CoachProfile,
    CoachProposal,
)
from app.infrastructure.db.models.auth import EmailToken, RefreshToken
from app.infrastructure.db.models.exercise import Exercise, exercise_equipment, exercise_muscle_groups
from app.infrastructure.db.models.rank import UserRankProgress
from app.infrastructure.db.models.routine import Routine, RoutineExercise
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.workout import WorkoutSession, WorkoutSet

EXPORT_FORMAT_VERSION = 1
# Columnas que nunca salen en la exportacion.
EXCLUDED_COLUMNS = {"password_hash", "token_hash"}

# Tablas con user_id directo. Orden de borrado: primero las que referencian a otras tablas del usuario.
USER_OWNED_MODELS: list[type[Base]] = [
    AiSessionSummary,
    AiSuggestion,
    AiTrainingPlan,
    AiCoachIntake,
    CoachPlannedSession,
    CoachProposal,
    CoachMemoryEvent,
    CoachConversation,
    CoachProfile,
    UserRankProgress,
]


class InvalidPasswordError(Exception):
    pass


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    return value


def _row(instance: Base) -> dict[str, Any]:
    return {
        column.key: _json_value(getattr(instance, column.key))
        for column in instance.__mapper__.columns
        if column.key not in EXCLUDED_COLUMNS
    }


class AccountService:
    def export_data(self, db: Session, user: User) -> dict[str, Any]:
        routines = list(db.scalars(select(Routine).where(Routine.user_id == user.id)).all())
        routine_ids = [routine.id for routine in routines]
        sessions = list(db.scalars(select(WorkoutSession).where(WorkoutSession.user_id == user.id)).all())
        session_ids = [session.id for session in sessions]
        data: dict[str, Any] = {
            "format_version": EXPORT_FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "user": _row(user),
            "routines": [_row(item) for item in routines],
            "routine_exercises": [
                _row(item)
                for item in db.scalars(select(RoutineExercise).where(RoutineExercise.routine_id.in_(routine_ids))).all()
            ]
            if routine_ids
            else [],
            "workout_sessions": [_row(item) for item in sessions],
            "workout_sets": [
                _row(item)
                for item in db.scalars(select(WorkoutSet).where(WorkoutSet.session_id.in_(session_ids))).all()
            ]
            if session_ids
            else [],
            "private_exercises": [
                _row(item)
                for item in db.scalars(
                    select(Exercise).where(Exercise.created_by_user_id == user.id, Exercise.is_global.is_(False))
                ).all()
            ],
        }
        for model in USER_OWNED_MODELS:
            data[model.__tablename__] = [
                _row(item) for item in db.scalars(select(model).where(model.user_id == user.id)).all()
            ]
        return data

    def delete_account(self, db: Session, user: User, password: str) -> None:
        if not verify_password(password, user.password_hash):
            raise InvalidPasswordError

        user_id = user.id
        session_ids = select(WorkoutSession.id).where(WorkoutSession.user_id == user_id)
        routine_ids = select(Routine.id).where(Routine.user_id == user_id)
        private_exercise_ids = select(Exercise.id).where(
            Exercise.created_by_user_id == user_id, Exercise.is_global.is_(False)
        )

        for model in USER_OWNED_MODELS:
            db.execute(delete(model).where(model.user_id == user_id))
        db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        db.execute(delete(EmailToken).where(EmailToken.user_id == user_id))
        db.execute(delete(WorkoutSet).where(WorkoutSet.session_id.in_(session_ids)))
        db.execute(delete(WorkoutSession).where(WorkoutSession.user_id == user_id))
        db.execute(delete(RoutineExercise).where(RoutineExercise.routine_id.in_(routine_ids)))
        db.execute(delete(Routine).where(Routine.user_id == user_id))
        db.execute(delete(exercise_muscle_groups).where(exercise_muscle_groups.c.exercise_id.in_(private_exercise_ids)))
        db.execute(delete(exercise_equipment).where(exercise_equipment.c.exercise_id.in_(private_exercise_ids)))
        db.execute(delete(Exercise).where(Exercise.created_by_user_id == user_id, Exercise.is_global.is_(False)))
        # Ejercicios globales creados por el usuario (si los hubiera) se conservan sin autoria.
        db.execute(update(Exercise).where(Exercise.created_by_user_id == user_id).values(created_by_user_id=None))
        db.execute(delete(User).where(User.id == user_id))
        db.commit()


account_service = AccountService()
