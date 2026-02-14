from __future__ import annotations

import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
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
    snapshots = relationship("TaxPropertySnapshot", back_populates="bot")
    configs = relationship("BotConfig", back_populates="bot")


class BotConfig(Base):
    __tablename__ = "bot_configs"
    __table_args__ = (UniqueConstraint("bot_id", "key", name="uq_bot_configs_bot_id_key"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    key = Column(String(255), nullable=False)
    config_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bot = relationship("Bot", back_populates="configs")


class BotRun(Base):
    __tablename__ = "bot_runs"

    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_summary = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=False, default=dict)

    bot = relationship("Bot", back_populates="runs")
    property_snapshots = relationship("TaxPropertySnapshot", back_populates="run")


class TaxPropertySnapshot(Base):
    __tablename__ = "tax_property_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("bot_runs.id"), nullable=False, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False, index=True)
    source_url = Column(String(1024), nullable=False)
    source_account_number = Column(String(64), nullable=True, index=True)
    final_url = Column(String(1024), nullable=False)
    property_address = Column(String(1024), nullable=False, index=True)
    total_due = Column(Numeric(12, 2), nullable=False)
    tables_json = Column(JSON, nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    run = relationship("BotRun", back_populates="property_snapshots")
    bot = relationship("Bot", back_populates="snapshots")
