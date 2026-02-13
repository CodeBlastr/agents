from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import Base


class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    runs = relationship("BotRun", back_populates="bot")
    snapshots = relationship("TaxSnapshot", back_populates="bot")
    notifications = relationship("Notification", back_populates="bot")


class BotRun(Base):
    __tablename__ = "bot_runs"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(32), nullable=False)
    error = Column(Text)

    bot = relationship("Bot", back_populates="runs")


class TaxSnapshot(Base):
    __tablename__ = "tax_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    parcel_id = Column(String(255), nullable=False, index=True)
    portal_url = Column(String(1024), nullable=False, index=True)
    balance_due = Column(Numeric(12, 2), nullable=False)
    paid_status = Column(String(64), nullable=False)
    due_date = Column(String(64), nullable=False)
    raw_json = Column(JSON, nullable=False)

    bot = relationship("Bot", back_populates="snapshots")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    channel = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)

    bot = relationship("Bot", back_populates="notifications")
