from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


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
