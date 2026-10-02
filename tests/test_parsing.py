"""Tests for parsing, on small hand-written filings."""

from pathlib import Path

import pytest

from sec_10k_rag.parsing.html_text import html_to_text
from sec_10k_rag.parsing.sections import split_into_items
from sec_10k_rag.parsing.sgml import extract_10k_html

BUSINESS: str = "We make electric cars. " * 100  # long enough to be the real Item 1
# A sentence that starts with "Item 1A" but is far too long to be a heading
CROSS_REF: str = "Item 1A describes our risks, " + "which matter a lot, " * 10

FILING: str = f"""Table of Contents
Item 1. | Business | 4
Item 1A. | Risk Factors | 10
Item 7. | Management's Discussion and Analysis | 30
PART I
Item 1. Business
{BUSINESS}
{CROSS_REF}
Item 1A. Risk Factors
Our stock price may be volatile.
Item 1A
Supply chains may break.
Item 7. Management's Discussion and Analysis
Revenue grew.
"""


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def test_skips_table_of_contents_and_page_headers() -> None:
    sections = split_into_items(FILING)
    assert [s.item for s in sections] == ["1", "1A", "7"]
    assert sections[0].text.startswith("Item 1. Business\nWe make")
    assert CROSS_REF.strip() in sections[0].text  # the long sentence is not a heading
    # the repeated "Item 1A" page header stays inside Item 1A
    assert "Supply chains may break." in sections[1].text
    assert sections[2].title == "Management's Discussion and Analysis"


def test_html_to_text_drops_hidden_xbrl_and_keeps_table_cells() -> None:
    html = """<html><body>
    <div style="display:none"><ix:header>hidden facts</ix:header></div>
    <p>Item&#160;1A.&#160;Risk Factors</p>
    <table><tr><td>Revenue</td><td></td><td>$ 97,690</td></tr></table>
    <p>12</p>
    </body></html>"""
    assert html_to_text(html) == "Item 1A. Risk Factors\nRevenue | $ 97,690"


def test_extract_10k_html_picks_the_10k_document() -> None:
    submission = (
        "<DOCUMENT>\n<TYPE>10-K\n<TEXT>\n<XBRL>\n<html>main</html>\n</XBRL>\n</TEXT>\n</DOCUMENT>\n"
        "<DOCUMENT>\n<TYPE>EX-21.1\n<TEXT>\n<html>subsidiaries</html>\n</TEXT>\n</DOCUMENT>\n"
    )
    assert extract_10k_html(submission).strip() == "<html>main</html>"


def test_missing_item_is_skipped(fixtures_dir: Path) -> None:
    file_path = fixtures_dir / "missing_items_in_filing.txt"
    test_data = file_path.read_text(encoding="utf-8")
    sections = split_into_items(test_data)
    expected_items = ["1", "7"]
    assert [section.item for section in sections] == expected_items
    assert sections[0].text.startswith("Item 1. Business\nWe design")
    assert sections[-1].text.endswith("Total revenues grew 3% in 2025.")
