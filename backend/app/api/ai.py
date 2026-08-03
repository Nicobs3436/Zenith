from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.users import get_current_user
from app.application.ai_coach_service import (
    AiRoutineAnalysisNotFoundError,
    AiSuggestionCannotApplyError,
    AiSuggestionNotFoundError,
    AiSuggestionNotPendingError,
    ai_coach_service,
)
from app.application.ai_coach_question_service import (
    AiCoachQuestionCannotAnswerError,
    AiCoachQuestionNotFoundError,
    ai_coach_question_service,
)
from app.application.ai_coach_intake_service import (
    AiCoachIntakeCannotGenerateError,
    ai_coach_intake_service,
)
from app.application.coach_v2_service import (
    CoachV2CannotGenerateError,
    CoachV2ProposalNotFoundError,
    CoachV2ProposalNotPendingError,
    coach_v2_service,
)
from app.application.coach_service import (
    CoachCannotGenerateError,
    CoachPlanNotDraftError,
    CoachPlanNotFoundError,
    coach_service,
)
from app.application.ai_session_summary_service import (
    AiSessionSummaryCannotGenerateError,
    AiSessionSummaryNotFoundError,
    ai_session_summary_service,
)
from app.application.ai_training_plan_service import (
    AiTrainingPlanCannotGenerateError,
    AiTrainingPlanNotDraftError,
    AiTrainingPlanNotFoundError,
    ai_training_plan_service,
)
from app.domain.ai import (
    AiCoachIntakeMessageRequest,
    AiCoachIntakeRead,
    AiCoachQuestionRead,
    AiCoachQuestionRequest,
    AiSessionSummaryRead,
    AiSuggestionRead,
    AiTrainingPlanGenerateRequest,
    AiTrainingPlanModifyRequest,
    AiTrainingPlanRead,
    CoachPlannedSessionRead,
    CoachMessageRequest,
    CoachProposalRead,
    CoachStateRead,
    CoachV2MessageRequest,
    CoachV2StateRead,
)
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/coach", response_model=CoachStateRead)
def get_coach_state(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return coach_service.get_state(db, current_user)


@router.post("/coach/messages", response_model=CoachStateRead)
def add_coach_message(
    data: CoachMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return coach_service.add_message(db, current_user, data)


@router.post("/coach/plans", response_model=AiTrainingPlanRead, status_code=status.HTTP_201_CREATED)
def generate_coach_plan(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_service.generate_plan(db, current_user)
    except CoachCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/coach/plans/{plan_id}/accept", response_model=AiTrainingPlanRead)
def accept_coach_plan(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_service.accept_plan(db, plan_id, current_user)
    except CoachPlanNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coach plan not found.") from error
    except CoachPlanNotDraftError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coach plan is not a draft.") from error
    except CoachCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/coach/plans/{plan_id}/reject", response_model=AiTrainingPlanRead)
def reject_coach_plan(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_service.reject_plan(db, plan_id, current_user)
    except CoachPlanNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coach plan not found.") from error
    except CoachPlanNotDraftError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coach plan is not a draft.") from error


@router.post("/coach/plans/{plan_id}/modify", response_model=AiTrainingPlanRead, status_code=status.HTTP_201_CREATED)
def modify_coach_plan(
    plan_id: UUID,
    data: AiTrainingPlanModifyRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_service.modify_plan(db, plan_id, current_user, data)
    except CoachPlanNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coach plan not found.") from error
    except CoachPlanNotDraftError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coach plan is not a draft.") from error
    except CoachCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/coach/reset", response_model=CoachStateRead)
def reset_coach(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return coach_service.reset(db, current_user)


@router.get("/coach/v2", response_model=CoachV2StateRead)
def get_coach_v2_state(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return coach_v2_service.get_state(db, current_user)


@router.post("/coach/v2/messages", response_model=CoachV2StateRead)
def add_coach_v2_message(
    data: CoachV2MessageRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return coach_v2_service.add_message(db, current_user, data)


@router.post("/coach/v2/generate-plan", response_model=AiTrainingPlanRead, status_code=status.HTTP_201_CREATED)
def generate_coach_v2_plan(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_v2_service.generate_plan(db, current_user)
    except CoachV2CannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/coach/v2/planned-sessions/generate", response_model=CoachPlannedSessionRead, status_code=status.HTTP_201_CREATED)
def generate_coach_v2_planned_session(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_v2_service.generate_planned_session(db, current_user)
    except CoachV2CannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/coach/v2/proposals/{proposal_id}/accept", response_model=CoachProposalRead)
def accept_coach_v2_proposal(
    proposal_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_v2_service.accept_proposal(db, proposal_id, current_user)
    except CoachV2ProposalNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found.") from error
    except CoachV2ProposalNotPendingError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal is not pending.") from error


@router.post("/coach/v2/proposals/{proposal_id}/reject", response_model=CoachProposalRead)
def reject_coach_v2_proposal(
    proposal_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return coach_v2_service.reject_proposal(db, proposal_id, current_user)
    except CoachV2ProposalNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found.") from error
    except CoachV2ProposalNotPendingError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Proposal is not pending.") from error


@router.post("/coach/v2/reset", response_model=CoachV2StateRead)
def reset_coach_v2(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return coach_v2_service.reset(db, current_user)


@router.post("/suggestions/generate", response_model=list[AiSuggestionRead], status_code=status.HTTP_201_CREATED)
def generate_suggestions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return ai_coach_service.generate_suggestions(db, current_user)


@router.get("/suggestions", response_model=list[AiSuggestionRead])
def list_suggestions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return ai_coach_service.list_suggestions(db, current_user)


@router.post("/routines/{routine_id}/analyze-goal", response_model=list[AiSuggestionRead], status_code=status.HTTP_201_CREATED)
def analyze_routine_goal(
    routine_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_coach_service.analyze_routine_goal(db, routine_id, current_user)
    except AiRoutineAnalysisNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routine not found.") from error


@router.post("/coach/questions", response_model=AiCoachQuestionRead)
def answer_coach_question(
    data: AiCoachQuestionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_coach_question_service.answer_question(db, current_user, data)
    except AiCoachQuestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referenced training data not found.") from error
    except AiCoachQuestionCannotAnswerError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/coach/intake", response_model=AiCoachIntakeRead)
def get_coach_intake(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return ai_coach_intake_service.get_intake(db, current_user)


@router.post("/coach/intake/messages", response_model=AiCoachIntakeRead)
def add_coach_intake_message(
    data: AiCoachIntakeMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return ai_coach_intake_service.add_message(db, current_user, data)


@router.post("/coach/intake/generate-plan", response_model=AiTrainingPlanRead, status_code=status.HTTP_201_CREATED)
def generate_plan_from_coach_intake(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_coach_intake_service.generate_plan(db, current_user)
    except AiCoachIntakeCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/coach/intake/reset", response_model=AiCoachIntakeRead)
def reset_coach_intake(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return ai_coach_intake_service.reset_intake(db, current_user)


@router.post("/suggestions/{suggestion_id}/accept", response_model=AiSuggestionRead)
def accept_suggestion(
    suggestion_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_coach_service.accept_suggestion(db, suggestion_id, current_user)
    except AiSuggestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found.") from error
    except AiSuggestionNotPendingError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Suggestion is not pending.") from error
    except AiSuggestionCannotApplyError as error:
        raise HTTPException(status_code=422, detail="Suggestion cannot be applied.") from error


@router.post("/suggestions/{suggestion_id}/reject", response_model=AiSuggestionRead)
def reject_suggestion(
    suggestion_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_coach_service.reject_suggestion(db, suggestion_id, current_user)
    except AiSuggestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found.") from error
    except AiSuggestionNotPendingError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Suggestion is not pending.") from error


@router.post("/training-plans/generate", response_model=AiTrainingPlanRead, status_code=status.HTTP_201_CREATED)
def generate_training_plan(
    data: AiTrainingPlanGenerateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_training_plan_service.generate_plan(db, current_user, data)
    except AiTrainingPlanCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/training-plans", response_model=list[AiTrainingPlanRead])
def list_training_plans(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return ai_training_plan_service.list_plans(db, current_user)


@router.get("/training-plans/{plan_id}", response_model=AiTrainingPlanRead)
def get_training_plan(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_training_plan_service.get_plan(db, plan_id, current_user)
    except AiTrainingPlanNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training plan not found.") from error


@router.post("/training-plans/{plan_id}/accept", response_model=AiTrainingPlanRead)
def accept_training_plan(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_training_plan_service.accept_plan(db, plan_id, current_user)
    except AiTrainingPlanNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training plan not found.") from error
    except AiTrainingPlanNotDraftError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Training plan is not a draft.") from error
    except AiTrainingPlanCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/training-plans/{plan_id}/reject", response_model=AiTrainingPlanRead)
def reject_training_plan(
    plan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_training_plan_service.reject_plan(db, plan_id, current_user)
    except AiTrainingPlanNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training plan not found.") from error
    except AiTrainingPlanNotDraftError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Training plan is not a draft.") from error


@router.post("/training-plans/{plan_id}/modify", response_model=AiTrainingPlanRead, status_code=status.HTTP_201_CREATED)
def modify_training_plan(
    plan_id: UUID,
    data: AiTrainingPlanModifyRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_training_plan_service.modify_plan(db, plan_id, current_user, data)
    except AiTrainingPlanNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training plan not found.") from error
    except AiTrainingPlanNotDraftError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Training plan is not a draft.") from error
    except AiTrainingPlanCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/session-summaries/{session_id}/generate", response_model=AiSessionSummaryRead, status_code=status.HTTP_201_CREATED)
def generate_session_summary(
    session_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_session_summary_service.generate_summary(db, session_id, current_user)
    except AiSessionSummaryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout session not found.") from error
    except AiSessionSummaryCannotGenerateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/session-summaries/{session_id}", response_model=AiSessionSummaryRead)
def get_session_summary(
    session_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return ai_session_summary_service.get_summary(db, session_id, current_user)
    except AiSessionSummaryNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session summary not found.") from error
