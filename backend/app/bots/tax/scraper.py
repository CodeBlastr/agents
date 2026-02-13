import os
from decimal import Decimal


def scrape_tax_data() -> dict:
    use_real = os.getenv("USE_REAL_SCRAPER", "0") == "1"
    if use_real:
        return _scrape_with_playwright()

    return {
        "parcel_id": "P-12345",
        "portal_url": "https://county.example.gov/tax",
        "balance_due": Decimal("1245.67"),
        "paid_status": "unpaid",
        "due_date": "2026-04-15",
        "raw_json": {
            "source": "stub",
            "note": "Deterministic fake data for local testing",
            "parcel_id": "P-12345",
            "balance_due": "1245.67",
            "paid_status": "unpaid",
            "due_date": "2026-04-15",
        },
    }


def _scrape_with_playwright() -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com", timeout=10000)
        title = page.title()
        browser.close()

    return {
        "parcel_id": "P-12345",
        "portal_url": "https://county.example.gov/tax",
        "balance_due": Decimal("1245.67"),
        "paid_status": "unpaid",
        "due_date": "2026-04-15",
        "raw_json": {"source": "playwright", "title": title},
    }
