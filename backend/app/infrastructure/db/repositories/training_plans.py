from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.ai import AiTrainingPlan


class AiTrainingPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: UUID,
        goal: str,
        level: str,
        days_per_week: int,
        session_duration_minutes: int,
        available_equipment: list[str],
        physical_limitations: str | None,
        sensitive_data_acknowledged: bool,
        priorities: list[str],
        plan_payload: dict,
        explanation: str,
        risk_notes: str | None,
        confidence: str | None,
        input_summary: dict,
        provider: str,
        model: str | None,
        fallback_used: bool,
    ) -> AiTrainingPlan:
        plan = AiTrainingPlan(
            user_id=user_id,
            status="draft",
            goal=goal,
            level=level,
            days_per_week=days_per_week,
            session_duration_minutes=session_duration_minutes,
            available_equipment=available_equipment,
            physical_limitations=physical_limitations,
            sensitive_data_acknowledged=sensitive_data_acknowledged,
            priorities=priorities,
            plan_payload=plan_payload,
            explanation=explanation,
            risk_notes=risk_notes,
            confidence=confidence,
            input_summary=input_summary,
            provider=provider,
            model=model,
            fallback_used=fallback_used,
        )
        self.db.add(plan)
        self.db.flush()
        return plan

    def list_by_user(self, user_id: UUID) -> list[AiTrainingPlan]:
        statement = (
            select(AiTrainingPlan).where(AiTrainingPlan.user_id == user_id).order_by(AiTrainingPlan.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def get_by_user(self, plan_id: UUID, user_id: UUID, *, for_update: bool = False) -> AiTrainingPlan | None:
        statement = select(AiTrainingPlan).where(AiTrainingPlan.id == plan_id, AiTrainingPlan.user_id == user_id)
        if for_update:
            # Bloquea la fila en PostgreSQL: dos "aceptar" simultaneos no crean rutinas duplicadas.
            statement = statement.with_for_update()
        return self.db.scalar(statement)
