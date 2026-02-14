from decimal import Decimal

from app.bots.tax.scraper import _extract_property_address, _extract_total_due


def test_extract_property_address_prefers_label() -> None:
    tables = [
        {
            "rows": [
                ["Label", "Value"],
                ["Property Address", "104 MOONEY AVE."],
            ]
        }
    ]
    assert _extract_property_address(tables, fallback="Unknown") == "104 MOONEY AVE."


def test_extract_total_due_uses_total_rows() -> None:
    tables = [
        {
            "rows": [
                ["Line", "Amount"],
                ["City Tax", "$250.00"],
                ["TOTAL", "$1,234.56"],
            ]
        }
    ]
    assert _extract_total_due(tables) == Decimal("1234.56")
