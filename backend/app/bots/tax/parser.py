from decimal import Decimal


def parse_tax_data(scraped: dict) -> dict:
    return {
        "parcel_id": scraped["parcel_id"],
        "portal_url": scraped["portal_url"],
        "balance_due": Decimal(str(scraped["balance_due"])),
        "paid_status": scraped["paid_status"],
        "due_date": scraped["due_date"],
        "raw_json": scraped["raw_json"],
    }
