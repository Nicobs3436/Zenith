from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.rank import Rank, UserRankProgress


class RankRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_ranks(self) -> list[Rank]:
        return list(self.db.scalars(select(Rank).order_by(Rank.sort_order)).all())

    def get_rank_for_score(self, score: Decimal) -> Rank:
        rank = self.db.scalar(select(Rank).where(Rank.min_score <= score).order_by(Rank.min_score.desc()).limit(1))
        if rank is None:
            rank = self.db.scalar(select(Rank).order_by(Rank.min_score).limit(1))
        if rank is None:
            raise RuntimeError("Ranks are not seeded.")
        return rank

    def get_next_rank_for_score(self, score: Decimal) -> Rank | None:
        return self.db.scalar(select(Rank).where(Rank.min_score > score).order_by(Rank.min_score).limit(1))

    def save_progress(
        self,
        *,
        user_id: UUID,
        rank_id: UUID,
        score: Decimal,
        volume_score: Decimal,
        progression_score: Decimal,
        breadth_score: Decimal,
    ) -> UserRankProgress:
        progress = UserRankProgress(
            user_id=user_id,
            rank_id=rank_id,
            score=score,
            volume_score=volume_score,
            progression_score=progression_score,
            breadth_score=breadth_score,
        )
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress
