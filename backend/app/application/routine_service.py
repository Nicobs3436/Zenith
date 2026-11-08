from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.routines import RoutineCreate, WorkoutSessionCreate
from app.application.rank_service import rank_service
from app.infrastructure.db.models.routine import Routine
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.workout import WorkoutSession
from app.infrastructure.db.repositories.exercises import ExerciseRepository
from app.infrastructure.db.repositories.routines import RoutineRepository, WorkoutSessionRepository


class RoutineReferenceError(Exception):
    pass


class RoutineService:
    def list_routines(self, db: Session, user: User) -> list[Routine]:
        return RoutineRepository(db).list_by_user(user.id)

    def get_routine(self, db: Session, routine_id: UUID, user: User) -> Routine | None:
        return RoutineRepository(db).get_by_user(routine_id, user.id)

    def create_routine(self, db: Session, data: RoutineCreate, user: User) -> Routine:
        exercise_repository = ExerciseRepository(db)
        routine_repository = RoutineRepository(db)
        for exercise in data.exercises:
            if exercise_repository.get_accessible(exercise.exercise_id, user.id) is None:
                raise RoutineReferenceError("exercise_id")

        routine = routine_repository.create(
            user_id=user.id,
            name=data.name,
            description=data.description,
            goal=data.goal,
        )
        for exercise in data.exercises:
            routine_repository.add_exercise(
                routine=routine,
                exercise_id=exercise.exercise_id,
                position=exercise.position,
                target_sets=exercise.target_sets,
                target_reps_min=exercise.target_reps_min,
                target_reps_max=exercise.target_reps_max,
                target_weight_value=exercise.target_weight_value,
                target_weight_unit=exercise.target_weight_unit,
                target_rpe=exercise.target_rpe,
                target_rir=exercise.target_rir,
                rest_seconds=exercise.rest_seconds,
                notes=exercise.notes,
            )
        return routine_repository.save_and_get(routine)

    def update_routine(self, db: Session, routine_id: UUID, data: RoutineCreate, user: User) -> Routine | None:
        exercise_repository = ExerciseRepository(db)
        routine_repository = RoutineRepository(db)
        routine = routine_repository.get_by_user(routine_id, user.id)
        if routine is None:
            return None

        for exercise in data.exercises:
            if exercise_repository.get_accessible(exercise.exercise_id, user.id) is None:
                raise RoutineReferenceError("exercise_id")

        routine.name = data.name
        routine.description = data.description
        routine.goal = data.goal
        routine_repository.replace_exercises(routine)
        for exercise in data.exercises:
            routine_repository.add_exercise(
                routine=routine,
                exercise_id=exercise.exercise_id,
                position=exercise.position,
                target_sets=exercise.target_sets,
                target_reps_min=exercise.target_reps_min,
                target_reps_max=exercise.target_reps_max,
                target_weight_value=exercise.target_weight_value,
                target_weight_unit=exercise.target_weight_unit,
                target_rpe=exercise.target_rpe,
                target_rir=exercise.target_rir,
                rest_seconds=exercise.rest_seconds,
                notes=exercise.notes,
            )
        return routine_repository.save_and_get(routine)

    def delete_routine(self, db: Session, routine_id: UUID, user: User) -> bool:
        routine_repository = RoutineRepository(db)
        routine = routine_repository.get_by_user(routine_id, user.id)
        if routine is None:
            return False
        routine_repository.soft_delete(routine)
        return True

    def list_sessions(self, db: Session, user: User) -> list[WorkoutSession]:
        return WorkoutSessionRepository(db).list_by_user(user.id)

    def get_session(self, db: Session, session_id: UUID, user: User) -> WorkoutSession | None:
        return WorkoutSessionRepository(db).get_by_user(session_id, user.id)

    def create_session(self, db: Session, data: WorkoutSessionCreate, user: User) -> WorkoutSession:
        exercise_repository = ExerciseRepository(db)
        routine_repository = RoutineRepository(db)
        session_repository = WorkoutSessionRepository(db)

        if data.routine_id is not None and routine_repository.get_by_user(data.routine_id, user.id) is None:
            raise RoutineReferenceError("routine_id")

        for workout_set in data.sets:
            if exercise_repository.get_accessible(workout_set.exercise_id, user.id) is None:
                raise RoutineReferenceError("exercise_id")

        session = session_repository.create(
            user_id=user.id,
            routine_id=data.routine_id,
            started_at=data.started_at,
            finished_at=data.finished_at,
            timezone=data.timezone,
            notes=data.notes,
        )
        for workout_set in data.sets:
            session_repository.add_set(
                session=session,
                exercise_id=workout_set.exercise_id,
                set_number=workout_set.set_number,
                reps=workout_set.reps,
                weight_value=workout_set.weight_value,
                weight_unit=workout_set.weight_unit,
                rpe=workout_set.rpe,
                rir=workout_set.rir,
                rest_seconds=workout_set.rest_seconds,
                notes=workout_set.notes,
            )
        saved_session = session_repository.save_and_get(session)
        self._recalculate_rank_if_seeded(db, user)
        return saved_session

    def update_session(
        self, db: Session, session_id: UUID, data: WorkoutSessionCreate, user: User
    ) -> WorkoutSession | None:
        exercise_repository = ExerciseRepository(db)
        routine_repository = RoutineRepository(db)
        session_repository = WorkoutSessionRepository(db)
        session = session_repository.get_by_user(session_id, user.id)
        if session is None:
            return None

        # Mantener el routine_id original esta permitido aunque la rutina se haya borrado (soft delete):
        # el historial conserva su vinculo. Solo se valida al cambiarlo por otra rutina.
        routine_changed = data.routine_id != session.routine_id
        if (
            routine_changed
            and data.routine_id is not None
            and routine_repository.get_by_user(data.routine_id, user.id) is None
        ):
            raise RoutineReferenceError("routine_id")

        for workout_set in data.sets:
            if exercise_repository.get_accessible(workout_set.exercise_id, user.id) is None:
                raise RoutineReferenceError("exercise_id")

        session.routine_id = data.routine_id
        session.started_at = data.started_at
        session.finished_at = data.finished_at
        session.timezone = data.timezone
        session.notes = data.notes
        session_repository.replace_sets(session)
        for workout_set in data.sets:
            session_repository.add_set(
                session=session,
                exercise_id=workout_set.exercise_id,
                set_number=workout_set.set_number,
                reps=workout_set.reps,
                weight_value=workout_set.weight_value,
                weight_unit=workout_set.weight_unit,
                rpe=workout_set.rpe,
                rir=workout_set.rir,
                rest_seconds=workout_set.rest_seconds,
                notes=workout_set.notes,
            )
        saved_session = session_repository.save_and_get(session)
        self._recalculate_rank_if_seeded(db, user)
        return saved_session

    def delete_session(self, db: Session, session_id: UUID, user: User) -> bool:
        session_repository = WorkoutSessionRepository(db)
        session = session_repository.get_by_user(session_id, user.id)
        if session is None:
            return False
        session_repository.soft_delete(session)
        self._recalculate_rank_if_seeded(db, user)
        return True

    def _recalculate_rank_if_seeded(self, db: Session, user: User) -> None:
        try:
            rank_service.recalculate_rank(db, user)
        except RuntimeError as error:
            if str(error) != "Ranks are not seeded.":
                raise


routine_service = RoutineService()
