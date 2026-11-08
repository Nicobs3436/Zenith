from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.auth import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        rotated_from_id: UUID | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            rotated_from_id=rotated_from_id,
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def revoke_all_for_user(self, user_id: UUID) -> None:
        now = datetime.now(UTC)
        for token in self.db.scalars(
            select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        ).all():
            token.revoked_at = now
        self.db.flush()

    def revoke(self, token: RefreshToken) -> RefreshToken:
        token.revoked_at = datetime.now(UTC)
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token
