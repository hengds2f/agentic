"""SQLAlchemy ORM models for persistence."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


class TripRow(Base):
    __tablename__ = "trips"

    id = Column(String, primary_key=True, default=_uuid)
    destination = Column(String, nullable=False, default="")
    origin = Column(String, default="")
    start_date = Column(String, default="")
    end_date = Column(String, default="")
    budget_total = Column(Float, default=0.0)
    budget_currency = Column(String, default="USD")
    mood = Column(String, default="relaxing")
    travelers_json = Column(JSON, default=list)
    interests_json = Column(JSON, default=list)
    constraints_json = Column(JSON, default=list)
    notes = Column(Text, default="")
    itinerary_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatRow(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=_uuid)
    trip_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    agent = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserPreferenceRow(Base):
    __tablename__ = "user_preferences"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False)
    preferences_json = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
