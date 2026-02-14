from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Page
from playwright.async_api import async_playwright

Money = Decimal
EventCallback = Callable[[dict[str, Any]], None]
_MONEY_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_account_number(url: str) -> str | None:
    return parse_qs(urlparse(url).query).get("number", [None])[0]


def _artifact_rel(path: Path, artifacts_root: Path) -> str:
    # Persist absolute-style paths rooted at /artifacts for easy UI mapping.
    rel = path.relative_to(artifacts_root)
    return f"/artifacts/{rel.as_posix()}"


def _parse_money(text: str) -> Money | None:
    if not text:
        return None
    match = _MONEY_RE.search(text)
    if not match:
        return None
    raw = re.sub(r"[^0-9.]", "", match.group(1))
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


async def _extract_tables(page: Page, table_selector: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    table_locator = page.locator(table_selector)
    table_count = await table_locator.count()

    for table_idx in range(table_count):
        rows_locator = table_locator.nth(table_idx).locator("tr")
        row_count = await rows_locator.count()
        rows: list[list[str]] = []

        for row_idx in range(row_count):
            cells_locator = rows_locator.nth(row_idx).locator("th, td")
            cell_count = await cells_locator.count()
            values: list[str] = []

            for cell_idx in range(cell_count):
                text = await cells_locator.nth(cell_idx).inner_text()
                cleaned = _normalize_text(text)
                if cleaned:
                    values.append(cleaned)

            if values:
                rows.append(values)

        if rows:
            tables.append({"table_index": table_idx, "rows": rows})

    return tables


def _extract_property_address(tables: list[dict[str, Any]], fallback: str) -> str:
    for table in tables:
        rows = table.get("rows", [])
        for row in rows:
            if len(row) >= 2 and row[0].strip().lower().rstrip(":") == "property address":
                return row[1]

        if len(rows) >= 2:
            headers = [cell.lower() for cell in rows[0]]
            for idx, header in enumerate(headers):
                if "property address" in header and idx < len(rows[1]):
                    candidate = rows[1][idx].strip()
                    if candidate and candidate.lower() not in {"property address", "property number"}:
                        return candidate

    return fallback


def _extract_total_due(tables: list[dict[str, Any]]) -> Money:
    totals: list[Money] = []

    for table in tables:
        for row in table.get("rows", []):
            if not row:
                continue
            if "total" in row[0].lower():
                for cell in reversed(row):
                    money = _parse_money(cell)
                    if money is not None:
                        totals.append(money)
                        break

    if totals:
        return sum(totals, Decimal("0.00"))

    fallback: Money | None = None
    for table in tables:
        for row in table.get("rows", []):
            for cell in row:
                money = _parse_money(cell)
                if money is not None and (fallback is None or money > fallback):
                    fallback = money

    return fallback if fallback is not None else Decimal("0.00")


def _build_redirect_chain(response) -> list[str]:
    if response is None:
        return []

    chain: list[str] = [response.url]
    request = response.request
    while request is not None and request.redirected_from is not None:
        request = request.redirected_from
        chain.append(request.url)
    chain.reverse()
    if chain[-1] != response.url:
        chain.append(response.url)
    return chain


async def _scrape_single_url(
    page: Page,
    source_url: str,
    artifacts_root: Path,
    run_dir: Path,
    index: int,
    table_selector: str,
    event_callback: EventCallback | None,
) -> dict[str, Any]:
    account_number = _extract_account_number(source_url)
    slug = account_number or f"url_{index}"
    url_dir = run_dir / f"{index:02d}_{slug}"
    url_dir.mkdir(parents=True, exist_ok=True)

    if event_callback:
        event_callback(
            {
                "type": "url_started",
                "source_url": source_url,
                "source_account_number": account_number,
                "property_index": index,
            }
        )

    before_path = url_dir / "before.png"
    await page.screenshot(path=str(before_path), full_page=True)

    try:
        response = await page.goto(source_url, wait_until="domcontentloaded", timeout=45000)
        if response is None:
            raise RuntimeError("No HTTP response received from source URL")

        await page.wait_for_function(
            """([startUrl, selector]) => {
                return window.location.href !== startUrl || !!document.querySelector(selector);
            }""",
            arg=[source_url, table_selector],
            timeout=15000,
        )
        await page.wait_for_selector(table_selector, timeout=20000)

        final_url = page.url
        redirect_chain = _build_redirect_chain(response)
        redirect_event = {
            "type": "url_redirect_observed",
            "source_url": source_url,
            "final_url": final_url,
            "source_account_number": account_number,
            "redirect_chain": redirect_chain,
            "redirected": final_url != source_url,
            "property_index": index,
        }
        if event_callback:
            event_callback(redirect_event)

        after_redirect_path = url_dir / "after_redirect.png"
        await page.screenshot(path=str(after_redirect_path), full_page=True)

        tables = await _extract_tables(page, table_selector)
        if not tables:
            raise RuntimeError("Structured table data not found on page")

        property_address = _extract_property_address(tables, fallback="")
        if not property_address:
            raise RuntimeError("Property address could not be extracted from structured table data")
        total_due = _extract_total_due(tables)

        parsed_path = url_dir / "parsed.png"
        await page.screenshot(path=str(parsed_path), full_page=True)

        url_result = {
            "status": "success",
            "source_url": source_url,
            "source_account_number": account_number,
            "final_url": final_url,
            "property_address": property_address,
            "total_due": str(total_due),
            "table_count": len(tables),
            "redirect_chain": redirect_chain,
            "artifacts": {
                "before": _artifact_rel(before_path, artifacts_root),
                "after_redirect": _artifact_rel(after_redirect_path, artifacts_root),
                "parsed": _artifact_rel(parsed_path, artifacts_root),
            },
        }

        if event_callback:
            event_callback(
                {
                    "type": "url_scraped",
                    "source_url": source_url,
                    "source_account_number": account_number,
                    "property_address": property_address,
                    "total_due": str(total_due),
                    "property_index": index,
                }
            )

        return {
            "url_result": url_result,
            "snapshot": {
                "source_url": source_url,
                "source_account_number": account_number,
                "final_url": final_url,
                "property_address": property_address,
                "total_due": str(total_due),
                "tables_json": tables,
                "metadata_json": {
                    "table_count": len(tables),
                    "redirect_chain": redirect_chain,
                    "artifacts": url_result["artifacts"],
                },
                "scraped_at": datetime.now(timezone.utc),
            },
        }

    except Exception as exc:
        error_path = url_dir / "error.png"
        try:
            await page.screenshot(path=str(error_path), full_page=True)
            error_artifact = _artifact_rel(error_path, artifacts_root)
        except Exception:
            error_artifact = ""

        excerpt = ""
        try:
            excerpt = _normalize_text((await page.inner_text("body"))[:500])
        except Exception:
            excerpt = ""

        error = f"{exc}"
        failure = {
            "status": "failed",
            "source_url": source_url,
            "source_account_number": account_number,
            "final_url": page.url,
            "error": error,
            "excerpt": excerpt,
            "artifacts": {
                "before": _artifact_rel(before_path, artifacts_root),
                "error": error_artifact,
            },
        }

        if event_callback:
            event_callback(
                {
                    "type": "url_failed",
                    "source_url": source_url,
                    "source_account_number": account_number,
                    "error": error,
                    "property_index": index,
                }
            )

        return {"url_result": failure, "snapshot": None}


async def _scrape_all_async(
    run_id: int,
    source_urls: list[str],
    artifacts_root: Path,
    event_callback: EventCallback | None,
    table_selector: str = "table",
) -> dict[str, Any]:
    run_dir = artifacts_root / "runs" / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    url_results: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        try:
            for index, source_url in enumerate(source_urls, start=1):
                page = await context.new_page()
                try:
                    outcome = await _scrape_single_url(
                        page=page,
                        source_url=source_url,
                        artifacts_root=artifacts_root,
                        run_dir=run_dir,
                        index=index,
                        table_selector=table_selector,
                        event_callback=event_callback,
                    )
                finally:
                    await page.close()

                url_results.append(outcome["url_result"])
                if outcome["snapshot"]:
                    snapshots.append(outcome["snapshot"])
        finally:
            await context.close()
            await browser.close()

    return {
        "run_id": run_id,
        "artifacts_root": _artifact_rel(run_dir, artifacts_root),
        "url_results": url_results,
        "snapshots": snapshots,
    }


def scrape_tax_data(
    run_id: int,
    source_urls: list[str],
    artifacts_dir: str,
    table_selector: str = "table",
    event_callback: EventCallback | None = None,
) -> dict[str, Any]:
    artifacts_root = Path(artifacts_dir)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    return asyncio.run(
        _scrape_all_async(
            run_id=run_id,
            source_urls=source_urls,
            artifacts_root=artifacts_root,
            event_callback=event_callback,
            table_selector=table_selector,
        )
    )


__all__ = [
    "scrape_tax_data",
    "_extract_property_address",
    "_extract_total_due",
]
