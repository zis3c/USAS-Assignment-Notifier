"""SQLAlchemy ORM models for the Assignment Notifier bot."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint

from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String, unique=True, index=True, nullable=False)
    student_id = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    password_blob = Column(LargeBinary, nullable=False)
    session_cookie_blob = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_checked_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    event_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    due_at = Column(DateTime, nullable=True)
    link = Column(String, nullable=True)
    first_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_user_event"),)


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True)
    is_maintenance = Column(Boolean, default=False)
    broadcast_count = Column(Integer, default=0)
