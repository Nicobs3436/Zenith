from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.infrastructure.db.models.exercise import Equipment, Exercise, MuscleGroup


class ExerciseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_accessible(self, user_id: UUID | None) -> list[Exercise]:
        statement = (
            select(Exercise)
            .options(selectinload(Exercise.muscle_groups), selectinload(Exercise.equipment))
            .order_by(Exercise.name)
        )
        if user_id is None:
            statement = statement.where(Exercise.is_global.is_(True))
        else:
            statement = statement.where(or_(Exercise.is_global.is_(True), Exercise.created_by_user_id == user_id))
        return list(self.db.scalars(statement).all())

    def get_accessible(self, exercise_id: UUID, user_id: UUID | None) -> Exercise | None:
        statement = (
            select(Exercise)
            .options(selectinload(Exercise.muscle_groups), selectinload(Exercise.equipment))
            .where(Exercise.id == exercise_id)
        )
        if user_id is None:
            statement = statement.where(Exercise.is_global.is_(True))
        else:
            statement = statement.where(or_(Exercise.is_global.is_(True), Exercise.created_by_user_id == user_id))
        return self.db.scalar(statement)

    def list_muscle_groups(self) -> list[MuscleGroup]:
        return list(self.db.scalars(select(MuscleGroup).order_by(MuscleGroup.name)).all())

    def list_equipment(self) -> list[Equipment]:
        return list(self.db.scalars(select(Equipment).order_by(Equipment.name)).all())

    def get_muscle_groups_by_ids(self, ids: list[UUID]) -> list[MuscleGroup]:
        if not ids:
            return []
        return list(self.db.scalars(select(MuscleGroup).where(MuscleGroup.id.in_(ids))).all())

    def get_equipment_by_ids(self, ids: list[UUID]) -> list[Equipment]:
        if not ids:
            return []
        return list(self.db.scalars(select(Equipment).where(Equipment.id.in_(ids))).all())

    def create_user_exercise(
        self,
        *,
        name: str,
        description: str | None,
        difficulty: str | None,
        technique_notes: str | None,
        created_by_user_id: UUID,
        muscle_groups: list[MuscleGroup],
        equipment: list[Equipment],
    ) -> Exercise:
        exercise = Exercise(
            name=name,
            description=description,
            difficulty=difficulty,
            technique_notes=technique_notes,
            is_global=False,
            created_by_user_id=created_by_user_id,
            muscle_groups=muscle_groups,
            equipment=equipment,
        )
        self.db.add(exercise)
        self.db.commit()
        self.db.refresh(exercise)
        return self.get_accessible(exercise.id, created_by_user_id) or exercise
