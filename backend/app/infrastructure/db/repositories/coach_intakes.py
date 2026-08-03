from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.ai import AiCoachIntake


class AiCoachIntakeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user(self, user_id: UUID) -> AiCoachIntake | None:
        statement = select(AiCoachIntake).where(AiCoachIntake.user_id == user_id)
        return self.db.scalar(statement)

    def get_or_create(self, user_id: UUID) -> AiCoachIntake:
        intake = self.get_by_user(user_id)
        if intake is not None:
            return intake
        intake = AiCoachIntake(user_id=user_id)
        self.db.add(intake)
        self.db.flush()
        return intake

    def reset(self, user_id: UUID) -> AiCoachIntake:
        intake = self.get_by_user(user_id)
        if intake is None:
            intake = AiCoachIntake(user_id=user_id)
            self.db.add(intake)
        else:
            intake.status = "collecting"
            intake.intake_summary = {}
            intake.recent_messages = []
            intake.missing_required_fields = []
            intake.ready_for_plan = False
            intake.sensitive_data_acknowledged = False
        self.db.flush()
        return intake
