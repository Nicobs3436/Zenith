from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.auth import EmailToken


class EmailTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, user_id: UUID, purpose: str, token_hash: str, expires_at: datetime) -> EmailToken:
        # Un enlace nuevo invalida los anteriores del mismo tipo.
        now = datetime.now(UTC)
        for previous in self.db.scalars(
            select(EmailToken).where(
                EmailToken.user_id == user_id, EmailToken.purpose == purpose, EmailToken.used_at.is_(None)
            )
        ).all():
            previous.used_at = now
        token = EmailToken(user_id=user_id, purpose=purpose, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        self.db.commit()
        return token

    def get_active(self, *, token_hash: str, purpose: str) -> EmailToken | None:
        token = self.db.scalar(
            select(EmailToken).where(EmailToken.token_hash == token_hash, EmailToken.purpose == purpose)
        )
        if token is None or token.used_at is not None:
            return None
        expires_at = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return None
        return token
