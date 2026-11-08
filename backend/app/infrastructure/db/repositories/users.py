from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        # lower() tambien cubre cuentas antiguas guardadas con mayusculas.
        return self.db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def create(self, *, email: str, username: str, password_hash: str) -> User:
        now = datetime.now(UTC)
        user = User(
            email=email,
            username=username,
            password_hash=password_hash,
            terms_accepted_at=now,
            adult_confirmed_at=now,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
