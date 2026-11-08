from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.ai import AiSuggestion
from app.infrastructure.db.models.routine import Routine, RoutineExercise


class AiSuggestionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_user(self, user_id: UUID) -> list[AiSuggestion]:
        statement = (
            select(AiSuggestion)
            .where(AiSuggestion.user_id == user_id)
            .order_by(AiSuggestion.created_at.desc(), AiSuggestion.id.desc())
        )
        return list(self.db.scalars(statement).all())

    def get_by_user(self, suggestion_id: UUID, user_id: UUID, *, for_update: bool = False) -> AiSuggestion | None:
        statement = select(AiSuggestion).where(AiSuggestion.id == suggestion_id, AiSuggestion.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_pending_by_routine_exercise(self, *, user_id: UUID, routine_exercise_id: UUID) -> list[AiSuggestion]:
        statement = select(AiSuggestion).where(
            AiSuggestion.user_id == user_id,
            AiSuggestion.routine_exercise_id == routine_exercise_id,
            AiSuggestion.status == "pending",
        )
        return list(self.db.scalars(statement).all())

    def find_matching_pending(
        self,
        *,
        user_id: UUID,
        routine_exercise_id: UUID,
        suggestion_type: str,
        apply_payload: dict,
    ) -> AiSuggestion | None:
        for suggestion in self.list_pending_by_routine_exercise(
            user_id=user_id,
            routine_exercise_id=routine_exercise_id,
        ):
            if suggestion.type == suggestion_type and suggestion.apply_payload == apply_payload:
                return suggestion
        return None

    def expire_pending_except(
        self,
        *,
        user_id: UUID,
        routine_exercise_id: UUID,
        keep_suggestion_id: UUID | None,
    ) -> None:
        for suggestion in self.list_pending_by_routine_exercise(
            user_id=user_id,
            routine_exercise_id=routine_exercise_id,
        ):
            if keep_suggestion_id is not None and suggestion.id == keep_suggestion_id:
                continue
            suggestion.status = "expired"
            suggestion.reviewed_at = datetime.now(UTC)

    def expire_pending_by_type_except(
        self,
        *,
        user_id: UUID,
        routine_exercise_id: UUID,
        suggestion_type: str,
        keep_suggestion_id: UUID | None,
    ) -> None:
        for suggestion in self.list_pending_by_routine_exercise(
            user_id=user_id,
            routine_exercise_id=routine_exercise_id,
        ):
            if suggestion.type != suggestion_type:
                continue
            if keep_suggestion_id is not None and suggestion.id == keep_suggestion_id:
                continue
            suggestion.status = "expired"
            suggestion.reviewed_at = datetime.now(UTC)

    def expire_pending_by_routine_type_except(
        self,
        *,
        user_id: UUID,
        routine_id: UUID,
        suggestion_type: str,
        keep_suggestion_ids: set[UUID],
    ) -> None:
        statement = select(AiSuggestion).where(
            AiSuggestion.user_id == user_id,
            AiSuggestion.routine_id == routine_id,
            AiSuggestion.type == suggestion_type,
            AiSuggestion.status == "pending",
        )
        for suggestion in self.db.scalars(statement):
            if suggestion.id in keep_suggestion_ids:
                continue
            suggestion.status = "expired"
            suggestion.reviewed_at = datetime.now(UTC)

    def create(
        self,
        *,
        user_id: UUID,
        routine_id: UUID | None,
        routine_exercise_id: UUID | None,
        exercise_id: UUID | None,
        suggestion_type: str,
        input_summary: dict,
        recommendation: str,
        explanation: str,
        risk_notes: str | None,
        confidence: str | None,
        apply_payload: dict,
    ) -> AiSuggestion:
        suggestion = AiSuggestion(
            user_id=user_id,
            routine_id=routine_id,
            routine_exercise_id=routine_exercise_id,
            exercise_id=exercise_id,
            type=suggestion_type,
            status="pending",
            input_summary=input_summary,
            recommendation=recommendation,
            explanation=explanation,
            risk_notes=risk_notes,
            confidence=confidence,
            apply_payload=apply_payload,
        )
        self.db.add(suggestion)
        self.db.flush()
        return suggestion

    def get_routine_exercise_for_user(
        self, routine_exercise_id: UUID, user_id: UUID
    ) -> tuple[Routine, RoutineExercise] | None:
        statement = (
            select(Routine, RoutineExercise)
            .join(RoutineExercise, RoutineExercise.routine_id == Routine.id)
            .where(
                RoutineExercise.id == routine_exercise_id,
                Routine.user_id == user_id,
                Routine.deleted_at.is_(None),
            )
        )
        row = self.db.execute(statement).first()
        if row is None:
            return None
        return row[0], row[1]
