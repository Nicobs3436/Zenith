from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.users import get_current_user
from app.application.auth_service import (
    DuplicateUserError,
    InvalidEmailTokenError,
    InvalidRefreshTokenError,
    TokenPair,
    auth_service,
)
from app.application.email_service import send_email_safely
from app.core.config import get_settings
from app.core.rate_limit import RateLimitExceededError, check_rate_limit
from app.domain.users import (
    EmailVerificationConfirm,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from app.infrastructure.db.models.user import User
from app.infrastructure.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# La web se identifica con esta cabecera. Un formulario o enlace de otro sitio no puede enviarla sin
# pasar por CORS, asi que ademas protege la cookie frente a CSRF.
WEB_CLIENT_HEADER = "X-Zenith-Client"


def client_host(request: Request) -> str:
    # La web llega por el proxy /api de Vercel: la IP real del usuario viene en esta cabecera.
    # Se puede falsear llamando a la API directamente, por eso el login tiene ademas un limite por email.
    vercel_ip = request.headers.get("x-vercel-forwarded-for", "").split(",")[0].strip()
    if vercel_ip:
        return vercel_ip
    return request.client.host if request.client else "unknown"


def is_web_client(request: Request) -> bool:
    return request.headers.get(WEB_CLIENT_HEADER, "").lower() == "web"


def raise_rate_limited() -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many attempts. Try again later.",
    )


def limit(key: str, attempts: int, window_seconds: int) -> None:
    try:
        check_rate_limit(key=key, limit=attempts, window_seconds=window_seconds)
    except RateLimitExceededError:
        raise_rate_limited()


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,  # type: ignore[arg-type]
        path=settings.refresh_cookie_path,
    )


def clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,  # type: ignore[arg-type]
        path=settings.refresh_cookie_path,
    )


def token_response(request: Request, response: Response, pair: TokenPair) -> TokenResponse:
    if is_web_client(request):
        # Web: el refresh token nunca toca JavaScript.
        set_refresh_cookie(response, pair.refresh_token)
        return TokenResponse(access_token=pair.access_token, refresh_token=None)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


def incoming_refresh_token(request: Request, body_token: str | None) -> str | None:
    if body_token:
        return body_token
    if is_web_client(request):
        return request.cookies.get(get_settings().refresh_cookie_name)
    return None


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    data: UserCreate, request: Request, background: BackgroundTasks, db: Annotated[Session, Depends(get_db)]
):
    settings = get_settings()
    limit(
        f"register:{client_host(request)}",
        settings.auth_register_rate_limit_attempts,
        settings.auth_register_rate_limit_window_seconds,
    )

    try:
        user = auth_service.register_user(db, data)
    except DuplicateUserError as error:
        field = str(error)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with this {field} already exists.",
        ) from error
    email = auth_service.build_verification_email(db, user)
    if email is not None:
        background.add_task(send_email_safely, email)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest, request: Request, response: Response, db: Annotated[Session, Depends(get_db)]
) -> TokenResponse:
    settings = get_settings()
    limit(
        f"login:{client_host(request)}:{str(data.email).lower()}",
        settings.auth_login_rate_limit_attempts,
        settings.auth_login_rate_limit_window_seconds,
    )
    # Limite por cuenta independiente de la IP: frena la fuerza bruta aunque se roten IPs.
    limit(
        f"login-email:{str(data.email).lower()}",
        settings.auth_login_email_rate_limit_attempts,
        settings.auth_login_email_rate_limit_window_seconds,
    )

    user = auth_service.authenticate_user(db, str(data.email), data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_response(request, response, auth_service.create_token_pair(db, user))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    data: RefreshTokenRequest | None = None,
) -> TokenResponse:
    token = incoming_refresh_token(request, data.refresh_token if data else None)
    try:
        if not token:
            raise InvalidRefreshTokenError
        pair = auth_service.refresh_token_pair(db, token)
    except InvalidRefreshTokenError as error:
        if is_web_client(request):
            clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    return token_response(request, response, pair)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    data: LogoutRequest | None = None,
) -> None:
    token = incoming_refresh_token(request, data.refresh_token if data else None)
    if token:
        auth_service.revoke_refresh_token(db, token)
    if is_web_client(request):
        clear_refresh_cookie(response)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    data: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    settings = get_settings()
    limit(
        f"password-reset:{client_host(request)}:{data.email}",
        settings.email_token_rate_limit_attempts,
        settings.email_token_rate_limit_window_seconds,
    )
    email = auth_service.build_password_reset_email(db, str(data.email))
    if email is not None:
        background.add_task(send_email_safely, email)
    # Misma respuesta exista o no la cuenta: no revela que emails estan registrados.
    return {"detail": "Si el email esta registrado, recibiras un enlace para restablecer la contrasena."}


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(
    data: PasswordResetConfirm, request: Request, db: Annotated[Session, Depends(get_db)]
) -> None:
    settings = get_settings()
    limit(
        f"password-reset-confirm:{client_host(request)}",
        settings.auth_login_rate_limit_attempts,
        settings.auth_login_rate_limit_window_seconds,
    )
    try:
        auth_service.reset_password(db, data.token, data.new_password)
    except InvalidEmailTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El enlace no es valido o ha caducado."
        ) from error


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(data: EmailVerificationConfirm, db: Annotated[Session, Depends(get_db)]) -> None:
    try:
        auth_service.verify_email(db, data.token)
    except InvalidEmailTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El enlace no es valido o ha caducado."
        ) from error


@router.post("/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
def resend_verification_email(
    background: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    settings = get_settings()
    limit(
        f"verify-resend:{current_user.id}",
        settings.email_token_rate_limit_attempts,
        settings.email_token_rate_limit_window_seconds,
    )
    email = auth_service.build_verification_email(db, current_user)
    if email is not None:
        background.add_task(send_email_safely, email)
    return {"detail": "Si tu email aun no esta verificado, te hemos enviado un nuevo enlace."}
