import asyncio
import hashlib
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

ARTIFACT_PATH = os.getenv("TAXBOT_ARTIFACT_PATH", "/artifacts/taxbot_run.png")
ERROR_SCREENSHOT_PATH = os.getenv("TAXBOT_ERROR_SCREENSHOT_PATH", "/artifacts/taxbot_last_error.png")
DEFAULT_BALANCE_REGEX = r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)"
MONEY_REGEX = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")


def _artifact_path(run_id: int | None, label: str, base_path: str = ARTIFACT_PATH) -> str:
    base = Path(base_path)
    stem = base.stem
    suffix = base.suffix or ".png"
    run_part = f"run_{run_id}" if run_id is not None else "run_unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return str(base.with_name(f"{stem}_{run_part}_{label}_{ts}{suffix}"))


def scrape_tax_data(
    parcel_id: str,
    portal_url: str,
    portal_profile: dict,
    run_id: int | None = None,
    event_callback=None,
) -> dict:
    scraper_mode = (portal_profile.get("scraper_mode") or "real").strip().lower()
    if scraper_mode == "stub":
        return _scrape_stub(parcel_id, portal_url)
    return asyncio.run(
        scrape_tax_portal(
            parcel_id,
            portal_url,
            portal_profile,
            run_id=run_id,
            event_callback=event_callback,
        )
    )


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
            "property_details": [],
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


async def _capture_artifact(page, run_id: int | None, label: str, artifacts: list[dict], event_callback=None) -> str:
    path = _artifact_path(run_id, label, ARTIFACT_PATH)
    await page.screenshot(path=path, full_page=True)
    entry = {"label": label, "path": path, "url": page.url}
    artifacts.append(entry)
    if event_callback:
        event_callback({"type": "screenshot_created", **entry})
    return path


async def _run_pre_steps(page, pre_steps: list[dict], run_id: int | None, artifacts: list[dict], event_callback=None):
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
        await _capture_artifact(page, run_id, f"pre_step_{idx}_{action}", artifacts, event_callback)


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


def _to_decimal(text: str) -> Decimal | None:
    if not text:
        return None
    match = MONEY_REGEX.search(text)
    if not match:
        return None
    cleaned = re.sub(r"[^0-9.]", "", match.group(1))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


async def _extract_table_data(page, table_selector: str) -> list[dict]:
    table_count = await page.locator(table_selector).count()
    tables: list[dict] = []
    for table_idx in range(table_count):
        table = page.locator(table_selector).nth(table_idx)
        heading = ""

        rows = table.locator("tr")
        row_count = await rows.count()
        row_data: list[list[str]] = []
        for row_idx in range(row_count):
            row = rows.nth(row_idx)
            cells = row.locator("th, td")
            cell_count = await cells.count()
            values = []
            for cell_idx in range(cell_count):
                text = (await cells.nth(cell_idx).inner_text()).strip()
                values.append(re.sub(r"\s+", " ", text))
            if values:
                row_data.append(values)

        if row_data:
            tables.append({"heading": heading, "rows": row_data})
    return tables


def _derive_total_due(tables: list[dict]) -> Decimal:
    totals: list[Decimal] = []
    for table in tables:
        for row in table.get("rows", []):
            if not row:
                continue
            first = row[0].strip().upper()
            if first == "TOTAL":
                for cell in reversed(row):
                    money = _to_decimal(cell)
                    if money is not None:
                        totals.append(money)
                        break

    if totals:
        return sum(totals, Decimal("0.00"))

    fallback: Decimal | None = None
    for table in tables:
        for row in table.get("rows", []):
            for cell in row:
                money = _to_decimal(cell)
                if money is not None and (fallback is None or money > fallback):
                    fallback = money
    return fallback if fallback is not None else Decimal("0.00")


def _extract_property_identity(tables: list[dict]) -> tuple[str | None, str | None, str | None]:
    property_number = None
    tax_map = None
    property_address = None
    for table in tables:
        rows = table.get("rows", [])
        if len(rows) < 2:
            continue
        headers = [c.strip().lower() for c in rows[0]]
        values = rows[1]
        for idx, header in enumerate(headers):
            value = values[idx] if idx < len(values) else None
            if value is None:
                continue
            if "property number" in header:
                property_number = value
            elif "tax map" in header:
                tax_map = value
            elif "property address" in header:
                property_address = value
    return property_number, tax_map, property_address


def _derive_address_from_url(url: str) -> str:
    match = re.search(r"[?&]number=([^&#]+)", url)
    if match:
        return f"Property {match.group(1)}"
    return url


async def _scrape_direct_property_urls(
    page,
    run_id: int | None,
    artifacts: list[dict],
    event_callback,
    direct_property_urls: list[str],
    detail_table_selector: str,
    max_properties: int,
) -> tuple[list[dict], Decimal]:
    details: list[dict] = []
    aggregate_total = Decimal("0.00")

    for idx, url in enumerate(direct_property_urls, start=1):
        if max_properties > 0 and len(details) >= max_properties:
            break

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as exc:
            await _capture_artifact(page, run_id, f"direct_property_{idx}_goto_error", artifacts, event_callback)
            if event_callback:
                event_callback(
                    {
                        "type": "property_row_skipped",
                        "row_index": idx - 1,
                        "property_index": idx,
                        "reason": f"failed loading direct url: {exc}",
                        "property_label": url,
                    }
                )
            continue

        if detail_table_selector.strip() and detail_table_selector.strip() not in {"*"}:
            try:
                await page.locator(detail_table_selector).first.wait_for(timeout=15000)
            except PlaywrightTimeoutError:
                await _capture_artifact(page, run_id, f"direct_property_{idx}_detail_wait_timeout", artifacts, event_callback)
                if event_callback:
                    event_callback(
                        {
                            "type": "property_row_skipped",
                            "row_index": idx - 1,
                            "property_index": idx,
                            "reason": f"detail selector did not appear: {detail_table_selector}",
                            "property_label": url,
                        }
                    )
                continue

        await _capture_artifact(page, run_id, f"direct_property_{idx}_detail", artifacts, event_callback)

        tables = await _extract_table_data(page, detail_table_selector)
        total_due = _derive_total_due(tables)
        property_number, tax_map, property_address = _extract_property_identity(tables)
        if not property_address:
            property_address = _derive_address_from_url(url)

        detail = {
            "row_index": idx - 1,
            "property_number": property_number,
            "tax_map": tax_map,
            "property_address": property_address,
            "total_due": str(total_due),
            "tables": tables,
            "detail_url": page.url,
            "source_url": url,
        }
        details.append(detail)
        aggregate_total += total_due

        if event_callback:
            event_callback(
                {
                    "type": "property_scraped",
                    "property_index": idx,
                    "property_address": property_address,
                    "total_due": str(total_due),
                    "property_number": property_number,
                    "tax_map": tax_map,
                }
            )

    return details, aggregate_total


async def _wait_for_detail_page_transition(page, previous_url: str, timeout_ms: int = 15000):
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_function(
        """([prevUrl]) => {
            if (window.location.href !== prevUrl) return true;
            const backToResults = Array.from(document.querySelectorAll('a, button, input[type=button], input[type=submit]'))
                .some((el) => /back\\s+to\\s+results/i.test((el.innerText || el.value || '').trim()));
            return backToResults;
        }""",
        [previous_url],
        timeout=timeout_ms,
    )


async def _open_property_detail(page, link, detail_table_selector: str):
    previous_url = page.url
    await link.click()

    try:
        await _wait_for_detail_page_transition(page, previous_url)
        return
    except PlaywrightTimeoutError:
        href = await link.get_attribute("href")
        if href and not href.strip().lower().startswith("javascript"):
            await page.goto(urljoin(previous_url, href), wait_until="domcontentloaded", timeout=30000)
            await _wait_for_detail_page_transition(page, previous_url)
            return

        if detail_table_selector.strip() and detail_table_selector.strip() not in {"table", "*"}:
            await page.locator(detail_table_selector).first.wait_for(timeout=15000)
            return

        raise


async def _resolve_results_locators(page, row_selector: str, first_link_selector: str) -> tuple[str, str]:
    candidates = [
        (row_selector, first_link_selector),
        ("#tblList > tbody > tr", "td:nth-child(1) a"),
        ("#tblList tbody tr", "td:nth-child(1) a"),
        ("#tblList tbody tr", "td a"),
        ("table tbody tr", "td:nth-child(1) a"),
    ]

    for cand_row_selector, cand_link_selector in candidates:
        rows = page.locator(cand_row_selector)
        if await rows.count() == 0:
            continue
        first_row = rows.first
        if await first_row.locator(cand_link_selector).count() > 0:
            return cand_row_selector, cand_link_selector

    return row_selector, first_link_selector


async def _scrape_multi_property_tax_data(
    page,
    run_id: int | None,
    artifacts: list[dict],
    event_callback,
    row_selector: str,
    first_link_selector: str,
    detail_table_selector: str,
    results_selector: str | None,
    max_properties: int,
) -> tuple[list[dict], Decimal]:
    requested_row_selector = row_selector
    requested_link_selector = first_link_selector
    row_selector, first_link_selector = await _resolve_results_locators(page, row_selector, first_link_selector)
    if event_callback and (row_selector != requested_row_selector or first_link_selector != requested_link_selector):
        event_callback(
            {
                "type": "results_locator_resolved",
                "requested_row_selector": requested_row_selector,
                "requested_link_selector": requested_link_selector,
                "row_selector": row_selector,
                "link_selector": first_link_selector,
            }
        )
    await page.locator(row_selector).first.wait_for(timeout=15000)
    details: list[dict] = []
    aggregate_total = Decimal("0.00")
    processed = 0
    row_index = 0

    while max_properties <= 0 or processed < max_properties:
        rows = page.locator(row_selector)
        row_count = await rows.count()
        if row_index >= row_count:
            break

        row = rows.nth(row_index)
        link = row.locator(first_link_selector).first
        if await link.count() == 0:
            row_index += 1
            continue

        link_text = (await link.inner_text()).strip()
        try:
            await _open_property_detail(page, link, detail_table_selector)
        except PlaywrightTimeoutError:
            await _capture_artifact(
                page,
                run_id,
                f"property_{processed + 1}_detail_wait_timeout",
                artifacts,
                event_callback,
            )
            if event_callback:
                event_callback(
                    {
                        "type": "property_row_skipped",
                        "row_index": row_index,
                        "property_index": processed + 1,
                        "reason": f"detail selector did not appear: {detail_table_selector}",
                        "property_label": link_text,
                    }
                )
            row_index += 1
            continue
        except Exception as exc:
            await _capture_artifact(
                page,
                run_id,
                f"property_{processed + 1}_detail_click_error",
                artifacts,
                event_callback,
            )
            if event_callback:
                event_callback(
                    {
                        "type": "property_row_skipped",
                        "row_index": row_index,
                        "property_index": processed + 1,
                        "reason": f"failed opening detail page: {exc}",
                        "property_label": link_text,
                    }
                )
            row_index += 1
            continue

        await _capture_artifact(page, run_id, f"property_{processed + 1}_detail", artifacts, event_callback)

        tables = await _extract_table_data(page, detail_table_selector)
        total_due = _derive_total_due(tables)
        property_number, tax_map, property_address = _extract_property_identity(tables)
        if not property_address:
            property_address = link_text

        property_detail = {
            "row_index": row_index,
            "property_number": property_number,
            "tax_map": tax_map,
            "property_address": property_address,
            "total_due": str(total_due),
            "tables": tables,
            "detail_url": page.url,
        }
        details.append(property_detail)
        aggregate_total += total_due

        if event_callback:
            event_callback(
                {
                    "type": "property_scraped",
                    "property_index": processed + 1,
                    "property_address": property_address,
                    "total_due": str(total_due),
                    "property_number": property_number,
                    "tax_map": tax_map,
                }
            )

        processed += 1

        back_button = page.get_by_text("Back to Results", exact=False).first
        if await back_button.count() > 0:
            await back_button.click()
        else:
            await page.go_back(wait_until="domcontentloaded")

        if results_selector:
            await page.locator(results_selector).first.wait_for(timeout=15000)
        else:
            await page.locator(row_selector).first.wait_for(timeout=15000)
        await _capture_artifact(page, run_id, f"property_{processed}_back_to_results", artifacts, event_callback)
        row_index += 1

    return details, aggregate_total


async def scrape_tax_portal(
    parcel_id: str,
    portal_url: str,
    portal_profile: dict,
    run_id: int | None = None,
    event_callback=None,
) -> dict:
    parcel_selector = portal_profile.get("parcel_selector")
    search_selector = portal_profile.get("search_button_selector")
    results_selector = portal_profile.get("results_container_selector")
    balance_regex = portal_profile.get("balance_regex") or DEFAULT_BALANCE_REGEX
    pre_steps = portal_profile.get("pre_steps") or []
    checkpoint_selector = portal_profile.get("checkpoint_selector")
    checkpoint_min_count = portal_profile.get("checkpoint_min_count")
    stop_after_checkpoint = bool(portal_profile.get("stop_after_checkpoint"))

    row_selector = portal_profile.get("results_row_selector") or "#tblList > tbody > tr"
    first_link_selector = portal_profile.get("row_first_link_selector") or "td:nth-child(1) a"
    detail_table_selector = portal_profile.get("detail_table_selector") or "table"
    raw_max_properties = portal_profile.get("max_properties")
    max_properties = int(raw_max_properties) if raw_max_properties is not None else 0
    direct_property_urls = [str(item).strip() for item in (portal_profile.get("direct_property_urls") or []) if str(item).strip()]

    page = None
    artifacts: list[dict] = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(portal_url, wait_until="networkidle", timeout=30000)
            await _capture_artifact(page, run_id, "initial_page", artifacts, event_callback)

            await _run_pre_steps(page, pre_steps, run_id, artifacts, event_callback)
            checkpoint = await _checkpoint_proof(page, checkpoint_selector, checkpoint_min_count)
            if checkpoint and event_callback:
                event_callback({"type": "checkpoint_validated", **checkpoint})
            if checkpoint:
                await _capture_artifact(page, run_id, "checkpoint", artifacts, event_callback)

            if stop_after_checkpoint:
                success_path = _artifact_path(run_id, "checkpoint", ARTIFACT_PATH)
                await page.screenshot(path=success_path, full_page=True)
                artifacts.append({"label": "checkpoint_final", "path": success_path, "url": page.url})
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
                        "property_details": [],
                        "artifacts": {
                            "checkpoint_screenshot": success_path,
                            "screenshots": artifacts,
                        },
                        **checkpoint,
                    },
                }

            if parcel_selector:
                candidate = page.locator(parcel_selector).first
                if await candidate.count() > 0:
                    await candidate.fill(parcel_id)

            if search_selector:
                button = page.locator(search_selector).first
                if await button.count() > 0:
                    await button.click()
                    await _capture_artifact(page, run_id, "after_search_click", artifacts, event_callback)
                    if results_selector:
                        await page.locator(results_selector).first.wait_for(timeout=10000)

            if direct_property_urls:
                property_details, aggregate_total = await _scrape_direct_property_urls(
                    page,
                    run_id,
                    artifacts,
                    event_callback,
                    direct_property_urls,
                    detail_table_selector,
                    max_properties,
                )
            else:
                property_details, aggregate_total = await _scrape_multi_property_tax_data(
                    page,
                    run_id,
                    artifacts,
                    event_callback,
                    row_selector,
                    first_link_selector,
                    detail_table_selector,
                    results_selector,
                    max_properties,
                )

            if not property_details:
                body_text = await page.inner_text("body")
                sample = body_text[:500]
                match = re.search(balance_regex, body_text)
                if not match:
                    raise RuntimeError(f"Could not extract properties or balance using regex: {balance_regex}")
                money = match.group(1) if match.groups() else match.group(0)
                cleaned = re.sub(r"[^0-9.]", "", money)
                aggregate_total = Decimal(cleaned)
                property_details = []
                extracted_text_sample = sample
            else:
                extracted_text_sample = ""

            success_path = _artifact_path(run_id, "success", ARTIFACT_PATH)
            await page.screenshot(path=success_path, full_page=True)
            artifacts.append({"label": "success", "path": success_path, "url": page.url})
            if event_callback:
                event_callback({"type": "screenshot_created", "label": "success", "path": success_path, "url": page.url})

            await browser.close()
            return {
                "mode": "real",
                "run_type": "multi_property_extract" if property_details else "full_extract",
                "parcel_id": parcel_id,
                "portal_url": portal_url,
                "balance_due": aggregate_total,
                "paid_status": None,
                "due_date": None,
                "raw_json": {
                    "mode": "real",
                    "portal_url": portal_url,
                    "parcel_id": parcel_id,
                    "extracted_text_sample": extracted_text_sample,
                    "regex_used": balance_regex,
                    "property_details": property_details,
                    "artifacts": {
                        "result_screenshot": success_path,
                        "screenshots": artifacts,
                    },
                    **checkpoint,
                },
            }
    except (PlaywrightTimeoutError, Exception) as exc:
        excerpt = ""
        error_path = _artifact_path(run_id, "error", ERROR_SCREENSHOT_PATH)
        if page is not None:
            try:
                await page.screenshot(path=error_path, full_page=True)
                artifacts.append({"label": "error", "path": error_path, "url": page.url})
                if event_callback:
                    event_callback({"type": "screenshot_created", "label": "error", "path": error_path, "url": page.url})
            except Exception:
                pass
            try:
                excerpt = (await page.inner_text("body"))[:500]
            except Exception:
                excerpt = ""
        raise RuntimeError(
            f"Real scrape failed: {exc}. Screenshot: {error_path}. Text excerpt: {excerpt}"
        ) from exc
