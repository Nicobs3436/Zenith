from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.exercise import Equipment, Exercise, MuscleGroup
from app.infrastructure.db.models.rank import Rank
from app.infrastructure.db.seed_data import EQUIPMENT, EXERCISES, MUSCLE_GROUPS, RANKS
from app.infrastructure.db.session import SessionLocal


def get_or_create_muscle_group(db: Session, name: str) -> MuscleGroup:
    muscle_group = db.scalar(select(MuscleGroup).where(MuscleGroup.name == name))
    if muscle_group is not None:
        return muscle_group

    muscle_group = MuscleGroup(name=name)
    db.add(muscle_group)
    db.flush()
    return muscle_group


def get_or_create_equipment(db: Session, name: str) -> Equipment:
    equipment = db.scalar(select(Equipment).where(Equipment.name == name))
    if equipment is not None:
        return equipment

    equipment = Equipment(name=name)
    db.add(equipment)
    db.flush()
    return equipment


def seed_database(db: Session) -> None:
    muscle_groups = {name: get_or_create_muscle_group(db, name) for name in MUSCLE_GROUPS}
    equipment_items = {name: get_or_create_equipment(db, name) for name in EQUIPMENT}

    for data in EXERCISES:
        exercise = db.scalar(select(Exercise).where(Exercise.name == data["name"], Exercise.is_global.is_(True)))
        for legacy_name in data.get("legacy_names", []):
            if exercise is not None:
                break
            exercise = db.scalar(select(Exercise).where(Exercise.name == legacy_name, Exercise.is_global.is_(True)))

        if exercise is None:
            db.add(
                Exercise(
                    name=data["name"],
                    description=data["description"],
                    difficulty=data["difficulty"],
                    technique_notes=data["technique_notes"],
                    is_global=True,
                    created_by_user_id=None,
                    muscle_groups=[muscle_groups[name] for name in data["muscle_groups"]],
                    equipment=[equipment_items[name] for name in data["equipment"]],
                )
            )
        else:
            exercise.name = data["name"]
            exercise.description = data["description"]
            exercise.difficulty = data["difficulty"]
            exercise.technique_notes = data["technique_notes"]
            exercise.muscle_groups = [muscle_groups[name] for name in data["muscle_groups"]]
            exercise.equipment = [equipment_items[name] for name in data["equipment"]]

    for data in RANKS:
        rank = db.scalar(select(Rank).where(Rank.name == data["name"]))
        if rank is None:
            db.add(
                Rank(
                    name=data["name"],
                    description=data["description"],
                    min_score=data["min_score"],
                    sort_order=data["sort_order"],
                )
            )
        else:
            rank.description = data["description"]
            rank.min_score = data["min_score"]
            rank.sort_order = data["sort_order"]

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
