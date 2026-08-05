from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.ai import CoachConversation, CoachMemoryEvent, CoachProfile


class CoachRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_profile(self, user_id: UUID) -> CoachProfile:
        profile = self.db.scalar(select(CoachProfile).where(CoachProfile.user_id == user_id))
        if profile is not None:
            return profile
        profile = CoachProfile(
            user_id=user_id,
            equipment=[],
            priorities=[],
            preferred_exercises=[],
            avoided_exercises=[],
            personal_data_acknowledged=False,
            sensitive_data_acknowledged=False,
        )
        self.db.add(profile)
        self.db.flush()
        return profile

    def get_or_create_conversation(self, user_id: UUID) -> CoachConversation:
        conversation = self.db.scalar(select(CoachConversation).where(CoachConversation.user_id == user_id))
        if conversation is not None:
            return conversation
        conversation = CoachConversation(user_id=user_id, recent_messages=[])
        self.db.add(conversation)
        self.db.flush()
        return conversation

    def add_memory(self, *, user_id: UUID, event_type: str, summary: str, payload: dict) -> CoachMemoryEvent:
        event = CoachMemoryEvent(user_id=user_id, event_type=event_type, summary=summary, payload=payload)
        self.db.add(event)
        self.db.flush()
        return event

    def reset(self, user_id: UUID) -> tuple[CoachProfile, CoachConversation]:
        profile = self.get_or_create_profile(user_id)
        profile.goal = None
        profile.secondary_goal = None
        profile.plan_horizon_weeks = None
        profile.biological_sex = None
        profile.age = None
        profile.height_cm = None
        profile.weight_kg = None
        profile.experience_level = None
        profile.training_age_months = None
        profile.days_per_week = None
        profile.session_duration_minutes = None
        profile.equipment = []
        profile.priorities = []
        profile.preferred_exercises = []
        profile.avoided_exercises = []
        profile.physical_limitations = None
        profile.sleep_quality = None
        profile.stress_level = None
        profile.current_fatigue = None
        profile.personal_data_acknowledged = False
        profile.sensitive_data_acknowledged = False
        profile.memory_summary = None
        conversation = self.get_or_create_conversation(user_id)
        conversation.phase = "onboarding"
        conversation.last_question = None
        conversation.recent_messages = []
        conversation.conversation_summary = None
        self.db.flush()
        return profile, conversation
