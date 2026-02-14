from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class BotSummary(BaseModel):
    slug: str
    name: str
    last_run: datetime | None = None
    last_status: str | None = None
    current_balance_due: Decimal | None = None
    previous_balance_due: Decimal | None = None
    changed: bool = False

    class Config:
        from_attributes = True


class TaxRunResult(BaseModel):
    bot_slug: str
    status: str
    run_id: int
    snapshot_id: int | None = None
    changed: bool = False
    message: str
    current_balance_due: Decimal | None = None
    previous_balance_due: Decimal | None = None


class PortalProfile(BaseModel):
    parcel_selector: str | None = None
    search_button_selector: str | None = None
    results_container_selector: str | None = None
    balance_regex: str | None = None
    pre_steps: list[dict] = Field(default_factory=list)
    checkpoint_selector: str | None = None
    checkpoint_min_count: int | None = None


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
