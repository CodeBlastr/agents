import asyncio
import hashlib
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

ERROR_SCREENSHOT_PATH = os.getenv("TAXBOT_ERROR_SCREENSHOT_PATH", "/artifacts/taxbot_last_error.png")
DEFAULT_BALANCE_REGEX = r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)"


def _artifact_path(run_id: int | None, label: str) -> str:
    base = Path(ERROR_SCREENSHOT_PATH)
    stem = base.stem
    suffix = base.suffix or ".png"
    run_part = f"run_{run_id}" if run_id is not None else "run_unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return str(base.with_name(f"{stem}_{run_part}_{label}_{ts}{suffix}"))


def scrape_tax_data(parcel_id: str, portal_url: str, portal_profile: dict, run_id: int | None = None) -> dict:
    use_real = os.getenv("USE_REAL_SCRAPER", "0") == "1"
    if use_real:
        return asyncio.run(scrape_tax_portal(parcel_id, portal_url, portal_profile, run_id=run_id))
    return _scrape_stub(parcel_id, portal_url)


def _scrape_stub(parcel_id: str, portal_url: str) -> dict:
    digest = hashlib.sha256(parcel_id.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    dollars = Decimal("100.00") + Decimal(seed % 5000) / Decimal("10")
    paid_status = "paid" if (seed % 3) == 0 else "unpaid"
    due_day = (seed % 27) + 1

    return {
        "mode": "stub",
        "run_type": "full_extract",
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


async def _get_locator(page, step: dict):
    selector = step.get("selector")
    text = step.get("text")
    if selector:
        return page.locator(selector).first
    if text:
        return page.get_by_text(text, exact=False).first
    raise RuntimeError("Step must include either 'selector' or 'text'")


async def _run_pre_steps(page, pre_steps: list[dict]):
    for idx, step in enumerate(pre_steps, start=1):
        action = (step.get("action") or "").strip().lower()
        timeout_ms = int(step.get("timeout_ms") or 10000)

        if action in {"click", "check", "fill", "wait_for_selector"}:
            locator = await _get_locator(page, step)

        if action == "click":
            await locator.wait_for(timeout=timeout_ms)
            await locator.click()
        elif action == "check":
            await locator.wait_for(timeout=timeout_ms)
            await locator.check()
        elif action == "fill":
            value = step.get("value")
            if value is None:
                raise RuntimeError(f"pre_step {idx}: fill requires 'value'")
            await locator.wait_for(timeout=timeout_ms)
            await locator.fill(str(value))
        elif action == "wait_for_selector":
            await locator.wait_for(timeout=timeout_ms)
        elif action == "wait_for_url":
            url = step.get("url")
            if not url:
                raise RuntimeError(f"pre_step {idx}: wait_for_url requires 'url'")
            await page.wait_for_url(url, timeout=timeout_ms)
        elif action == "wait_for_timeout":
            wait_ms = int(step.get("ms") or step.get("timeout_ms") or 1000)
            await page.wait_for_timeout(wait_ms)
        else:
            raise RuntimeError(
                "Unsupported pre-step action. Supported actions: "
                "click, check, fill, wait_for_selector, wait_for_url, wait_for_timeout"
            )


async def _checkpoint_proof(page, checkpoint_selector: str | None, checkpoint_min_count: int | None) -> dict:
    if not checkpoint_selector:
        return {}

    locator = page.locator(checkpoint_selector)
    await locator.first.wait_for(timeout=10000)
    count = await locator.count()

    if checkpoint_min_count is not None and count < checkpoint_min_count:
        raise RuntimeError(
            f"Checkpoint failed: expected at least {checkpoint_min_count} matches for "
            f"'{checkpoint_selector}', found {count}"
        )

    excerpt = (await page.inner_text("body"))[:500]
    return {
        "checkpoint_selector": checkpoint_selector,
        "checkpoint_count": count,
        "checkpoint_min_count": checkpoint_min_count,
        "checkpoint_url": page.url,
        "checkpoint_text_excerpt": excerpt,
    }


async def scrape_tax_portal(parcel_id: str, portal_url: str, portal_profile: dict, run_id: int | None = None) -> dict:
    parcel_selector = portal_profile.get("parcel_selector")
    search_selector = portal_profile.get("search_button_selector")
    results_selector = portal_profile.get("results_container_selector")
    balance_regex = portal_profile.get("balance_regex") or DEFAULT_BALANCE_REGEX
    pre_steps = portal_profile.get("pre_steps") or []
    checkpoint_selector = portal_profile.get("checkpoint_selector")
    checkpoint_min_count = portal_profile.get("checkpoint_min_count")
    stop_after_checkpoint = bool(portal_profile.get("stop_after_checkpoint"))

    page = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(portal_url, wait_until="networkidle", timeout=30000)

            await _run_pre_steps(page, pre_steps)
            checkpoint = await _checkpoint_proof(page, checkpoint_selector, checkpoint_min_count)

            if stop_after_checkpoint:
                success_path = _artifact_path(run_id, "checkpoint")
                await page.screenshot(path=success_path, full_page=True)
                await browser.close()
                return {
                    "mode": "real",
                    "run_type": "checkpoint_only",
                    "parcel_id": parcel_id,
                    "portal_url": portal_url,
                    "balance_due": Decimal("0.00"),
                    "paid_status": None,
                    "due_date": None,
                    "raw_json": {
                        "mode": "real",
                        "portal_url": portal_url,
                        "parcel_id": parcel_id,
                        "note": "Stopped after checkpoint by configuration",
                        "artifacts": {"checkpoint_screenshot": success_path},
                        **checkpoint,
                    },
                }

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

            success_path = _artifact_path(run_id, "success")
            await page.screenshot(path=success_path, full_page=True)

            await browser.close()
            return {
                "mode": "real",
                "run_type": "full_extract",
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
                    "artifacts": {"result_screenshot": success_path},
                    **checkpoint,
                },
            }
    except (PlaywrightTimeoutError, Exception) as exc:
        excerpt = ""
        error_path = _artifact_path(run_id, "error")
        if page is not None:
            try:
                await page.screenshot(path=error_path, full_page=True)
            except Exception:
                pass
            try:
                excerpt = (await page.inner_text("body"))[:500]
            except Exception:
                excerpt = ""
        raise RuntimeError(
            f"Real scrape failed: {exc}. Screenshot: {error_path}. Text excerpt: {excerpt}"
        ) from exc
