from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.domain.users import UserCreate
from app.infrastructure.db.models.user import User
from app.infrastructure.db.repositories.refresh_tokens import RefreshTokenRepository
from app.infrastructure.db.repositories.users import UserRepository


class DuplicateUserError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthService:
    def register_user(self, db: Session, data: UserCreate) -> User:
        repository = UserRepository(db)
        if repository.get_by_email(str(data.email)) is not None:
            raise DuplicateUserError("email")
        if repository.get_by_username(data.username) is not None:
            raise DuplicateUserError("username")

        try:
            return repository.create(
                email=str(data.email),
                username=data.username,
                password_hash=hash_password(data.password),
            )
        except IntegrityError as error:
            # Dos registros simultaneos con el mismo email/username: 409 en vez de 500.
            db.rollback()
            field = "username" if repository.get_by_email(str(data.email)) is None else "email"
            raise DuplicateUserError(field) from error

    def authenticate_user(self, db: Session, email: str, password: str) -> User | None:
        user = UserRepository(db).get_by_email(email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_user_access_token(self, user: User) -> str:
        return create_access_token(str(user.id))

    def create_token_pair(self, db: Session, user: User, rotated_from_id: UUID | None = None) -> TokenPair:
        settings = get_settings()
        refresh_token = create_refresh_token()
        RefreshTokenRepository(db).create(
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
            rotated_from_id=rotated_from_id,
        )
        return TokenPair(access_token=self.create_user_access_token(user), refresh_token=refresh_token)

    def refresh_token_pair(self, db: Session, refresh_token: str) -> TokenPair:
        repository = RefreshTokenRepository(db)
        persisted = repository.get_by_hash(hash_refresh_token(refresh_token))
        if persisted is None or persisted.revoked_at is not None:
            raise InvalidRefreshTokenError

        expires_at = persisted.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            repository.revoke(persisted)
            raise InvalidRefreshTokenError

        user = UserRepository(db).get_by_id(persisted.user_id)
        if user is None or not user.is_active:
            repository.revoke(persisted)
            raise InvalidRefreshTokenError

        repository.revoke(persisted)
        return self.create_token_pair(db, user, rotated_from_id=persisted.id)

    def revoke_refresh_token(self, db: Session, refresh_token: str) -> None:
        persisted = RefreshTokenRepository(db).get_by_hash(hash_refresh_token(refresh_token))
        if persisted is not None and persisted.revoked_at is None:
            RefreshTokenRepository(db).revoke(persisted)

    def get_user_from_token(self, db: Session, token: str) -> User | None:
        subject = decode_access_token(token)
        if subject is None:
            return None

        try:
            user_id = UUID(subject)
        except ValueError:
            return None

        user = UserRepository(db).get_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return user


auth_service = AuthService()
