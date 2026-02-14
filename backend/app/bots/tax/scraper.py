import asyncio
import hashlib
import os
import re
from decimal import Decimal

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

ERROR_SCREENSHOT_PATH = "/tmp/taxbot_last_error.png"
DEFAULT_BALANCE_REGEX = r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)"


def scrape_tax_data(parcel_id: str, portal_url: str, portal_profile: dict) -> dict:
    use_real = os.getenv("USE_REAL_SCRAPER", "0") == "1"
    if use_real:
        return asyncio.run(scrape_tax_portal(parcel_id, portal_url, portal_profile))
    return _scrape_stub(parcel_id, portal_url)


def _scrape_stub(parcel_id: str, portal_url: str) -> dict:
    digest = hashlib.sha256(parcel_id.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    dollars = Decimal("100.00") + Decimal(seed % 5000) / Decimal("10")
    paid_status = "paid" if (seed % 3) == 0 else "unpaid"
    due_day = (seed % 27) + 1

    return {
        "parcel_id": parcel_id,
        "portal_url": portal_url,
        "balance_due": dollars.quantize(Decimal("0.01")),
        "paid_status": paid_status,
        "due_date": f"2026-04-{due_day:02d}",
        "raw_json": {
            "mode": "stub",
            "note": "Deterministic fake data based on parcel_id",
            "parcel_id": parcel_id,
            "portal_url": portal_url,
        },
    }


async def scrape_tax_portal(parcel_id: str, portal_url: str, portal_profile: dict) -> dict:
    parcel_selector = portal_profile.get("parcel_selector")
    search_selector = portal_profile.get("search_button_selector")
    results_selector = portal_profile.get("results_container_selector")
    balance_regex = portal_profile.get("balance_regex") or DEFAULT_BALANCE_REGEX

    page = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(portal_url, wait_until="networkidle", timeout=20000)

            parcel_locator = None
            if parcel_selector:
                candidate = page.locator(parcel_selector).first
                if await candidate.count() > 0:
                    parcel_locator = candidate
            else:
                heuristics = [
                    'input[id*="parcel" i]',
                    'input[name*="parcel" i]',
                    'input[placeholder*="parcel" i]',
                    'input[id*="property" i]',
                    'input[name*="property" i]',
                ]
                for selector in heuristics:
                    candidate = page.locator(selector).first
                    if await candidate.count() > 0:
                        parcel_locator = candidate
                        break

            if parcel_locator is None:
                raise RuntimeError("Could not find parcel input field")

            await parcel_locator.fill(parcel_id)

            clicked = False
            if search_selector:
                button = page.locator(search_selector).first
                if await button.count() > 0:
                    await button.click()
                    clicked = True
            if not clicked:
                for selector in ['button:has-text("Search")', 'button:has-text("Submit")', 'input[type="submit"]']:
                    button = page.locator(selector).first
                    if await button.count() > 0:
                        await button.click()
                        clicked = True
                        break
            if not clicked:
                raise RuntimeError("Could not find search/submit button")

            if results_selector:
                await page.locator(results_selector).first.wait_for(timeout=10000)
            else:
                await page.wait_for_timeout(1000)

            body_text = await page.inner_text("body")
            sample = body_text[:500]
            match = re.search(balance_regex, body_text)
            if not match:
                raise RuntimeError(f"Could not extract balance using regex: {balance_regex}")

            money = match.group(1) if match.groups() else match.group(0)
            cleaned = re.sub(r"[^0-9.]", "", money)
            if not cleaned:
                raise RuntimeError("Extracted money value was empty after cleaning")

            await browser.close()
            return {
                "parcel_id": parcel_id,
                "portal_url": portal_url,
                "balance_due": Decimal(cleaned),
                "paid_status": None,
                "due_date": None,
                "raw_json": {
                    "mode": "real",
                    "portal_url": portal_url,
                    "parcel_id": parcel_id,
                    "extracted_text_sample": sample,
                    "regex_used": balance_regex,
                },
            }
    except (PlaywrightTimeoutError, Exception) as exc:
        excerpt = ""
        if page is not None:
            try:
                await page.screenshot(path=ERROR_SCREENSHOT_PATH, full_page=True)
            except Exception:
                pass
            try:
                excerpt = (await page.inner_text("body"))[:500]
            except Exception:
                excerpt = ""
        raise RuntimeError(
            f"Real scrape failed: {exc}. Screenshot: {ERROR_SCREENSHOT_PATH}. Text excerpt: {excerpt}"
        ) from exc
