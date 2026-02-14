from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

DEFAULT_URLS = [
    "https://syracuse.go2gov.net/faces/accounts?number=0562001300&src=SDG",
    "https://syracuse.go2gov.net/faces/accounts?number=1626103200&src=SDG",
    "https://syracuse.go2gov.net/faces/accounts?number=0716100700&src=SDG",
]

_AS_OF_RE = re.compile(
    r'<span[^>]*id="etaxTemplateForm:text2234"[^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
_TAX_STATUS_RE = re.compile(
    r'([0-9]+\s+TAX\s+INFORMATION\s+IS\s+NOT\s+AVAILABLE)',
    re.IGNORECASE,
)


@dataclass
class SyracuseTaxRecord:
    url: str
    account_number: str | None
    fetched_at_utc: str
    as_of_date: str | None
    tax_information_available: bool
    tax_status_message: str


def _extract_account_number(url: str) -> str | None:
    number = parse_qs(urlparse(url).query).get("number", [None])[0]
    return number


def _fetch_html(url: str, timeout_s: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; SyracuseTaxScraper/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout_s) as response:  # nosec B310 - trusted public URL input for this tool
        return response.read().decode("ISO-8859-1", errors="replace")


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def scrape_syracuse_tax_page(url: str) -> SyracuseTaxRecord:
    html = _fetch_html(url)

    as_of_match = _AS_OF_RE.search(html)
    as_of_date = _strip_html(as_of_match.group(1)) if as_of_match else None

    status_match = _TAX_STATUS_RE.search(html)
    status_message = _strip_html(status_match.group(1)) if status_match else "Tax information status not found"

    return SyracuseTaxRecord(
        url=url,
        account_number=_extract_account_number(url),
        fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        as_of_date=as_of_date,
        tax_information_available="NOT AVAILABLE" not in status_message.upper(),
        tax_status_message=status_message,
    )


def scrape_many(urls: Iterable[str]) -> list[SyracuseTaxRecord]:
    return [scrape_syracuse_tax_page(url) for url in urls]


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Syracuse go2gov account pages.")
    parser.add_argument("urls", nargs="*", help="Account URLs to scrape")
    parser.add_argument("--output", "-o", default="", help="Optional output JSON file path")
    args = parser.parse_args()

    urls = args.urls or DEFAULT_URLS
    records = [asdict(record) for record in scrape_many(urls)]

    payload = {
        "source": "syracuse.go2gov.net",
        "count": len(records),
        "records": records,
    }

    output_text = json.dumps(payload, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_text)
            f.write("\n")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
