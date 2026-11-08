from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.infrastructure.db.models.routine import Routine, RoutineExercise
from app.infrastructure.db.models.workout import WorkoutSession, WorkoutSet


class RoutineRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(self, user_id: UUID) -> list[Routine]:
        statement = (
            select(Routine)
            .options(selectinload(Routine.exercises))
            .where(Routine.user_id == user_id, Routine.deleted_at.is_(None))
            .order_by(Routine.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def get_by_user(self, routine_id: UUID, user_id: UUID) -> Routine | None:
        statement = (
            select(Routine)
            .options(selectinload(Routine.exercises))
            .where(Routine.id == routine_id, Routine.user_id == user_id, Routine.deleted_at.is_(None))
        )
        return self.db.scalar(statement)

    def create(self, *, user_id: UUID, name: str, description: str | None, goal: str | None) -> Routine:
        routine = Routine(user_id=user_id, name=name, description=description, goal=goal)
        self.db.add(routine)
        self.db.flush()
        return routine

    def add_exercise(
        self,
        *,
        routine: Routine,
        exercise_id: UUID,
        position: int,
        target_sets: int | None,
        target_reps_min: int | None,
        target_reps_max: int | None,
        target_weight_value,
        target_weight_unit: str | None,
        target_rpe,
        target_rir: int | None,
        rest_seconds: int | None,
        notes: str | None,
    ) -> None:
        self.db.add(
            RoutineExercise(
                routine_id=routine.id,
                exercise_id=exercise_id,
                position=position,
                target_sets=target_sets,
                target_reps_min=target_reps_min,
                target_reps_max=target_reps_max,
                target_weight_value=target_weight_value,
                target_weight_unit=target_weight_unit,
                target_rpe=target_rpe,
                target_rir=target_rir,
                rest_seconds=rest_seconds,
                notes=notes,
            )
        )

    def replace_exercises(self, routine: Routine) -> None:
        routine.exercises.clear()
        self.db.flush()

    def save_and_get(self, routine: Routine) -> Routine:
        self.db.commit()
        loaded = self.get_by_user(routine.id, routine.user_id)
        return loaded or routine

    def soft_delete(self, routine: Routine) -> None:
        routine.deleted_at = datetime.now(UTC)
        self.db.commit()


class WorkoutSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(self, user_id: UUID) -> list[WorkoutSession]:
        statement = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets))
            .where(WorkoutSession.user_id == user_id, WorkoutSession.deleted_at.is_(None))
            .order_by(WorkoutSession.started_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def get_by_user(self, session_id: UUID, user_id: UUID) -> WorkoutSession | None:
        statement = (
            select(WorkoutSession)
            .options(selectinload(WorkoutSession.sets))
            .where(
                WorkoutSession.id == session_id, WorkoutSession.user_id == user_id, WorkoutSession.deleted_at.is_(None)
            )
        )
        return self.db.scalar(statement)

    def create(
        self,
        *,
        user_id: UUID,
        routine_id: UUID | None,
        started_at,
        finished_at,
        timezone: str,
        notes: str | None,
    ) -> WorkoutSession:
        session = WorkoutSession(
            user_id=user_id,
            routine_id=routine_id,
            started_at=started_at,
            finished_at=finished_at,
            timezone=timezone,
            notes=notes,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def add_set(
        self,
        *,
        session: WorkoutSession,
        exercise_id: UUID,
        set_number: int,
        reps: int,
        weight_value,
        weight_unit: str | None,
        rpe,
        rir: int | None,
        rest_seconds: int | None,
        notes: str | None,
    ) -> None:
        self.db.add(
            WorkoutSet(
                session_id=session.id,
                exercise_id=exercise_id,
                set_number=set_number,
                reps=reps,
                weight_value=weight_value,
                weight_unit=weight_unit,
                rpe=rpe,
                rir=rir,
                rest_seconds=rest_seconds,
                notes=notes,
            )
        )

    def replace_sets(self, session: WorkoutSession) -> None:
        session.sets.clear()
        self.db.flush()

    def save_and_get(self, session: WorkoutSession) -> WorkoutSession:
        self.db.commit()
        loaded = self.get_by_user(session.id, session.user_id)
        return loaded or session

    def soft_delete(self, session: WorkoutSession) -> None:
        session.deleted_at = datetime.now(UTC)
        self.db.commit()
