from decimal import Decimal


def parse_tax_data(scraped: dict) -> dict:
    raw_json = dict(scraped.get("raw_json") or {})
    if "mode" in scraped:
        raw_json["mode"] = scraped["mode"]
    if "run_type" in scraped:
        raw_json["run_type"] = scraped["run_type"]

    return {
        "parcel_id": scraped["parcel_id"],
        "portal_url": scraped["portal_url"],
        "balance_due": Decimal(str(scraped["balance_due"])),
        "paid_status": scraped["paid_status"],
        "due_date": scraped["due_date"],
        "raw_json": raw_json,
    }
