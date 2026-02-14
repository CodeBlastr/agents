from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class BotSummary(BaseModel):
    slug: str
    name: str
    last_run: datetime | None = None
    last_status: str | None = None
    current_balance_due: Decimal | None = None
    previous_balance_due: Decimal | None = None
    changed: bool = False
    mode: str | None = None
    run_type: str | None = None

    class Config:
        from_attributes = True


class TaxPropertyDetailItem(BaseModel):
    id: int | None = None
    property_number: str | None = None
    tax_map: str | None = None
    property_address: str
    total_due: Decimal
    detail_json: dict = Field(default_factory=dict)


class TaxRunResult(BaseModel):
    bot_slug: str
    status: str
    run_id: int
    snapshot_id: int | None = None
    changed: bool = False
    message: str
    mode: str | None = None
    run_type: str | None = None
    current_balance_due: Decimal | None = None
    previous_balance_due: Decimal | None = None
    details: dict = Field(default_factory=dict)
    property_details: list[TaxPropertyDetailItem] = Field(default_factory=list)


class TaxRunDetails(BaseModel):
    run_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    snapshot_id: int | None = None
    mode: str | None = None
    run_type: str | None = None
    current_balance_due: Decimal | None = None
    previous_balance_due: Decimal | None = None
    details: dict = Field(default_factory=dict)
    property_details: list[TaxPropertyDetailItem] = Field(default_factory=list)


class PortalProfile(BaseModel):
    parcel_selector: str | None = None
    search_button_selector: str | None = None
    results_container_selector: str | None = None
    balance_regex: str | None = None
    pre_steps: list[dict] = Field(default_factory=list)
    checkpoint_selector: str | None = None
    checkpoint_min_count: int | None = None
    stop_after_checkpoint: bool = False
    scraper_mode: Literal["real", "stub"] = "real"
    results_row_selector: str | None = None
    row_first_link_selector: str | None = None
    detail_table_selector: str | None = None
    max_properties: int | None = 3


class TaxConfig(BaseModel):
    parcel_id: str
    portal_url: HttpUrl
    portal_profile: PortalProfile

    @field_validator("parcel_id")
    @classmethod
    def validate_parcel_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("parcel_id must be non-empty")
        return value.strip()


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    message: str
