"""All the data types for parsing. Only data lives here: no logic.

Frozen dataclasses are for values our own
code builds, which need no checking.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

SourceFormat = Literal["html", "txt"]


@dataclass(frozen=True)
class Company_facts:
    """Basic facts about a company."""

    ticker: str
    cik: str
    name: str
    fiscal_year_end: str
    taxonomy: str  # e.g., "us-gaap", "dei"


@dataclass(frozen=True)
class ManifestEntry:
    """One row of data/raw/<TICKER>/manifest.json (written by download.py)."""

    ticker: str
    cik: str
    fiscal_year: int
    accession: str
    filing_date: date
    report_date: date
    primary_document: str
    html_url: str
    txt_url: str


@dataclass(frozen=True)
class Section:
    """One Item of one 10-K, with everything needed to cite it later."""

    section_id: str  # "TSLA-2025-item1A"
    ticker: str
    cik: str
    fiscal_year: int
    report_date: date
    accession: str
    source_format: SourceFormat
    source_url: str
    item: str  # "1A"
    title: str  # "Risk Factors"
    n_chars: int
    text: str


@dataclass(frozen=True)
class Heading:
    """A line that looks like an Item heading."""

    item: str  # "1A"
    start: int  # character offset of the line in the text


@dataclass(frozen=True)
class RawSection:
    """An Item cut out of the text, before it is tagged with filing details."""

    item: str
    title: str
    text: str


@dataclass(frozen=True)
class SgmlDocument:
    """One <DOCUMENT> inside a full-submission .txt file."""

    doc_type: str  # "10-K", "EX-21.1", "GRAPHIC", ...
    text: str  # what sits between <TEXT> and </TEXT>
