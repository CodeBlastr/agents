from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_model: str


class BotRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error_summary: str | None = None


class BotSummary(BaseModel):
    slug: str
    name: str
    last_run_id: int | None = None
    last_run_status: str | None = None
    last_run_at: datetime | None = None
    last_error_summary: str | None = None
    latest_property_count: int = 0


class BotDetail(BaseModel):
    slug: str
    name: str
    source_urls: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    recent_runs: list[BotRunSummary] = Field(default_factory=list)


class PropertySnapshotItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    source_url: str
    source_account_number: str | None = None
    final_url: str
    property_address: str
    total_due: Decimal
    tables_json: list[dict]
    metadata_json: dict
    scraped_at: datetime


class RefreshResponse(BaseModel):
    run_id: int
    status: str


class RunDetails(BaseModel):
    run_id: int
    bot_slug: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error_summary: str | None = None
    details_json: dict = Field(default_factory=dict)
    property_snapshots: list[PropertySnapshotItem] = Field(default_factory=list)
