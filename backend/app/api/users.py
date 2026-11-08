from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.application.account_service import InvalidPasswordError, account_service
from app.application.auth_service import auth_service
from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceededError, check_rate_limit
from app.domain.users import AccountDeleteRequest, UserRead
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/users", tags=["users"])


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = auth_service.get_user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


@router.get("/me/export")
def export_current_user_data(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Descarga todos los datos del usuario en JSON (sin hashes de contrasena ni de tokens)."""
    response.headers["Cache-Control"] = "no-store"
    return account_service.export_data(db, current_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    data: AccountDeleteRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Elimina la cuenta y todos sus datos de forma permanente. Requiere la contrasena actual."""
    settings = get_settings()
    try:
        check_rate_limit(
            key=f"delete-account:{current_user.id}",
            limit=settings.auth_login_rate_limit_attempts,
            window_seconds=settings.auth_login_rate_limit_window_seconds,
        )
    except RateLimitExceededError as error:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Try again later.") from error
    try:
        account_service.delete_account(db, current_user, data.password)
    except InvalidPasswordError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contrasena incorrecta.") from error
