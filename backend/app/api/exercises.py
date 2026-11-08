from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.api.users import get_current_user
from app.application.auth_service import auth_service
from app.application.exercise_service import ExerciseReferenceError, exercise_service
from app.domain.exercises import ExerciseCreate, ExerciseRead, NamedReference
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db

optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
router = APIRouter(tags=["exercises"])


def get_optional_current_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    if token is None:
        return None
    user = auth_service.get_user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.get("/exercises", response_model=list[ExerciseRead])
def list_exercises(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
):
    return exercise_service.list_exercises(db, current_user)


@router.post("/exercises", response_model=ExerciseRead, status_code=status.HTTP_201_CREATED)
def create_exercise(
    data: ExerciseCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        return exercise_service.create_user_exercise(db, data, current_user)
    except ExerciseReferenceError as error:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {error}.",
        ) from error


@router.get("/exercises/{exercise_id}", response_model=ExerciseRead)
def get_exercise(
    exercise_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
):
    exercise = exercise_service.get_exercise(db, exercise_id, current_user)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found.")
    return exercise


@router.get("/muscle-groups", response_model=list[NamedReference])
def list_muscle_groups(db: Annotated[Session, Depends(get_db)]):
    return exercise_service.list_muscle_groups(db)


@router.get("/equipment", response_model=list[NamedReference])
def list_equipment(db: Annotated[Session, Depends(get_db)]):
    return exercise_service.list_equipment(db)
