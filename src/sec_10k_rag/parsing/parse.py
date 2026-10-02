"""Parse every downloaded 10-K into sections and save them as JSON Lines.

Run with: uv run python -m sec_10k_rag.parsing.parse

Everything here is a pure function except read_filing() and main(),
which do all the reading, printing and writing.
"""

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from sec_10k_rag.models import ManifestEntry, RawSection, Section, SourceFormat
from sec_10k_rag.parsing.html_text import html_to_text
from sec_10k_rag.parsing.sections import split_into_items
from sec_10k_rag.parsing.sgml import extract_10k_html

RAW_DIR = Path("data/raw")
OUT_FILE = Path("data/processed/sections.jsonl")


def load_manifest(manifest_json: bytes) -> list[ManifestEntry]:
    """Raw manifest.json bytes -> typed entries."""
    rows: list[dict[str, Any]] = json.loads(manifest_json)
    return [to_entry(row) for row in rows]


def to_entry(row: dict[str, Any]) -> ManifestEntry:
    """One raw JSON row -> a ManifestEntry, converting each field to its real type.

    A missing field raises KeyError; a bad number or date raises ValueError.
    """
    return ManifestEntry(
        ticker=str(row["ticker"]),
        cik=str(row["cik"]),
        fiscal_year=int(row["fiscal_year"]),
        accession=str(row["accession"]),
        filing_date=date.fromisoformat(row["filing_date"]),
        report_date=date.fromisoformat(row["report_date"]),
        primary_document=str(row["primary_document"]),
        html_url=str(row["html_url"]),
        txt_url=str(row["txt_url"]),
    )


def parse_html_filing(entry: ManifestEntry, html: bytes) -> list[Section]:
    """10k.html -> tagged sections."""
    return tag_sections(entry, split_into_items(html_to_text(html)), "html")


def parse_txt_filing(entry: ManifestEntry, submission: str) -> list[Section]:
    """full_submission.txt -> tagged sections."""
    html: str = extract_10k_html(submission)
    return tag_sections(entry, split_into_items(html_to_text(html)), "txt")


def tag_sections(
    entry: ManifestEntry, raw_sections: list[RawSection], source_format: SourceFormat
) -> list[Section]:
    """Attach company, year and source details to each raw section."""
    url: str = entry.html_url if source_format == "html" else entry.txt_url
    return [
        Section(
            section_id=f"{entry.ticker}-{entry.fiscal_year}-item{raw.item}",
            ticker=entry.ticker,
            cik=entry.cik,
            fiscal_year=entry.fiscal_year,
            report_date=entry.report_date,
            accession=entry.accession,
            source_format=source_format,
            source_url=url,
            item=raw.item,
            title=raw.title,
            n_chars=len(raw.text),
            text=raw.text,
        )
        for raw in raw_sections
    ]


def same_items(a: list[Section], b: list[Section]) -> bool:
    """Do both parses find the same Items in the same order?"""
    return [s.item for s in a] == [s.item for s in b]


def format_report(entry: ManifestEntry, sections: list[Section], match: bool) -> str:
    """A readable summary of one filing: its Items and their sizes."""
    status: str = "match" if match else "MISMATCH"
    header: str = f"{entry.ticker} {entry.fiscal_year}: {len(sections)} sections, "
    rows: list[str] = [f"    Item {s.item:<3} {s.n_chars:>9,} chars  {s.title}" for s in sections]
    return "\n".join([header + f"html vs txt {status}", *rows])


def to_jsonl(sections: list[Section]) -> str:
    """Sections -> JSON Lines text, one section per line."""
    return "".join(section_to_json(section) + "\n" for section in sections)


def section_to_json(section: Section) -> str:
    """One Section -> one line of JSON. default=str writes dates as "2025-01-26"."""
    return json.dumps(asdict(section), default=str, ensure_ascii=False)


def parse_filing(entry: ManifestEntry, html: bytes, submission: str) -> tuple[list[Section], str]:
    """Both files of one filing -> its sections (from the HTML) and a report."""
    from_html: list[Section] = parse_html_filing(entry, html)
    from_txt: list[Section] = parse_txt_filing(entry, submission)
    report: str = format_report(entry, from_html, same_items(from_html, from_txt))
    return from_html, report


def read_filing(entry: ManifestEntry) -> tuple[bytes, str]:
    """Read one filing's 10k.html and full_submission.txt from disk. (I/O)"""
    year_dir: Path = RAW_DIR / entry.ticker / str(entry.fiscal_year)
    html: bytes = (year_dir / "10k.html").read_bytes()
    submission: str = (year_dir / "full_submission.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    return html, submission


def main() -> None:
    sections: list[Section] = []
    for manifest_path in sorted(RAW_DIR.glob("*/manifest.json")):
        for entry in load_manifest(manifest_path.read_bytes()):
            html, submission = read_filing(entry)
            from_html, report = parse_filing(entry, html, submission)
            print(report)
            sections.extend(from_html)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(to_jsonl(sections), encoding="utf-8")
    print(f"wrote {len(sections)} sections to {OUT_FILE}")


if __name__ == "__main__":
    main()
