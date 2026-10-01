"""Download 10-K filings and SEC JSON data for a few companies.

Run with: uv run python -m sec_10k_rag.download
"""

import json
import os
import time
from pathlib import Path
from typing import Any, TypedDict

import httpx
from dotenv import load_dotenv

load_dotenv()

# Ticker -> CIK (the SEC's company id, always 10 digits with leading zeros)
COMPANIES = {
    "TSLA": "0001318605",
    "MSFT": "0000789019",
    "NVDA": "0001045810",
}

YEARS_PER_COMPANY = 3
RAW_DIR = Path("data/raw")


class Filing(TypedDict):
    """One 10-K filing, as picked from the submissions JSON."""

    accession: str
    filing_date: str
    report_date: str
    primary_document: str


client = httpx.Client(
    headers={"User-Agent": os.environ["SEC_USER_AGENT"]},
    timeout=60,
    follow_redirects=True,
)


def get(url: str) -> httpx.Response:
    """GET a URL politely: the SEC allows at most 10 requests per second."""
    time.sleep(0.2)
    response = client.get(url)
    response.raise_for_status()
    return response


def save(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    print(f"saved {path} ({len(content) / 1_000_000:.1f} MB)")


def latest_10ks(submissions: dict[str, Any], n: int) -> list[Filing]:
    """Pick the newest n 10-K filings from a company's submissions JSON.

    The SEC stores recent filings as parallel lists (one list per field),
    newest first, so index i in every list describes the same filing.
    """

    """
    submissions:
    {
        "name": "Tesla, Inc.",
        "filings": {
            "recent": {
                "form":            ["10-Q", "8-K", "10-K", ...],
                "accessionNumber": ["0001...", "0001...", "0001...", ...],
                "reportDate":      ["2026-06-30", "", "2025-12-31", ...],
                "primaryDocument": ["tsla-20260630.htm", ...]
            }
        }
    }
    """
    recent: dict[str, list[str]] = submissions["filings"]["recent"]
    filings: list[Filing] = []
    for i, form in enumerate(recent["form"]):
        if form != "10-K":
            continue
        filings.append(
            {
                "accession": recent["accessionNumber"][i],
                "filing_date": recent["reportDate"][i],
                "report_date": recent["reportDate"][i],
                "primary_document": recent["primaryDocument"][i],
            }
        )
        if len(filings) == n:
            break
    return filings[:n]


def download_company(ticker: str, cik: str) -> None:
    company_dir = RAW_DIR / ticker

    # 1. Filing history: every form the company has filed, with links
    submissions = get(f"https://data.sec.gov/submissions/CIK{cik}.json")
    save(company_dir / "submissions.json", submissions.content)

    # 2. Company facts: every XBRL financial number (revenue, net income, ...)
    facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
    save(company_dir / "companyfacts.json", facts.content)

    # 3. The 10-K documents themselves
    manifest: list[dict[str, str]] = []
    for filing in latest_10ks(submissions.json(), YEARS_PER_COMPANY):
        folder = filing["accession"].replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{folder}"
        fiscal_year = filing["report_date"][:4]
        year_dir = company_dir / fiscal_year

        html_url = f"{base}/{filing['primary_document']}"
        save(year_dir / "10k.html", get(html_url).content)

        txt_url = f"{base}/{filing['accession']}.txt"
        save(year_dir / "full_submission.txt", get(txt_url).content)

        manifest.append(
            {
                "ticker": ticker,
                "cik": cik,
                "fiscal_year": fiscal_year,
                "accession": filing["accession"],
                "filing_date": filing["filing_date"],
                "report_date": filing["report_date"],
                "primary_document": filing["primary_document"],
                # **filing,
                "html_url": html_url,
                "txt_url": txt_url,
            }
        )

    # 4. A manifest: where every file came from (needed later for citations)
    save(company_dir / "manifest.json", json.dumps(manifest, indent=2).encode())


def main() -> None:
    for ticker, cik in COMPANIES.items():
        print(f"--- {ticker} ---")
        download_company(ticker, cik)


if __name__ == "__main__":
    main()
