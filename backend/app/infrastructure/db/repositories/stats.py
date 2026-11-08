from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.infrastructure.db.models.exercise import Exercise
from app.infrastructure.db.models.workout import WorkoutSession, WorkoutSet

StatsRow = tuple[WorkoutSet, WorkoutSession, Exercise]


class StatsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_workout_sets(
        self,
        *,
        user_id: UUID,
        exercise_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[StatsRow]:
        statement = (
            select(WorkoutSet, WorkoutSession, Exercise)
            .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
            .join(Exercise, WorkoutSet.exercise_id == Exercise.id)
            .where(WorkoutSession.user_id == user_id, WorkoutSession.deleted_at.is_(None))
            .options(selectinload(Exercise.muscle_groups))
            .order_by(Exercise.name, WorkoutSession.started_at, WorkoutSet.set_number)
        )
        if exercise_id is not None:
            statement = statement.where(WorkoutSet.exercise_id == exercise_id)
        if start_date is not None:
            statement = statement.where(WorkoutSession.started_at >= start_date)
        if end_date is not None:
            statement = statement.where(WorkoutSession.started_at <= end_date)

        return [(row[0], row[1], row[2]) for row in self.db.execute(statement).all()]
