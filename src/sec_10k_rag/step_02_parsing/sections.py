"""Split the plain text of a 10-K into its Items (1, 1A, 7, ...)."""

import re

from sec_10k_rag.step_02_parsing.models import Heading, RawSection

# Every Item a 10-K can have, in the order they appear in the filing
ITEM_TITLES: dict[str, str] = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity",
    "6": "[Reserved]",
    "7": "Management's Discussion and Analysis",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements with Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership of Certain Beneficial Owners and Management",
    "13": "Certain Relationships and Related Transactions",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}
ITEM_RANK: dict[str, int] = {
    item: rank for rank, item in enumerate(ITEM_TITLES)
}

# A heading line: "Item 1A. Risk Factors", "ITEM 7 | MANAGEMENT'S ...",
# "Item 1C:"
# Longer item numbers come first in the group, so "1A" wins over "1".
HEADING: re.Pattern[str] = re.compile(
    r"^item\s+(1A|1B|1C|1|2|3|4|5|6|7A|7|8|9A|9B|9C|9|10|11|12|13|14|15|16)\b",
    re.IGNORECASE | re.MULTILINE,
)
MAX_HEADING_CHARS = (
    150  # longer lines are sentences that mention an Item, not headings
)
MIN_BUSINESS_CHARS = 1_000  # Item 1 (Business) is always at least this long


def split_into_items(text: str) -> list[RawSection]:
    """Plain text of a 10-K -> one RawSection per Item, in filing order."""
    headings: list[Heading] = find_headings(text)
    body: list[Heading] = headings[body_start(headings) :]
    return cut_sections(text, pick_body_headings(body))


def cut_sections(text: str, headings: list[Heading]) -> list[RawSection]:
    """Cut the text at each heading; each piece runs to the next heading."""
    ends: list[int] = [h.start for h in headings[1:]] + [len(text)]
    return [
        RawSection(
            item=h.item,
            title=ITEM_TITLES[h.item],
            text=text[h.start : end].strip(),
        )
        for h, end in zip(headings, ends, strict=True)
    ]


def line_length(text: str, start: int) -> int:
    """Length of the line that begins at offset `start`."""
    end: int = text.find("\n", start)
    return (end if end != -1 else len(text)) - start


def find_headings(text: str) -> list[Heading]:
    """Every short line that starts like an Item heading, in document order."""
    return [
        Heading(item=match.group(1).upper(), start=match.start())
        for match in HEADING.finditer(text)
        if line_length(text, match.start()) <= MAX_HEADING_CHARS
    ]


def body_start(headings: list[Heading]) -> int:
    """Index of the real "Item 1" heading, right after the table of contents.

    In the table of contents, "Item 1" is followed a line later by "Item 1A".
    In the body, "Item 1. Business" is followed by pages of text.
    """
    for i, heading in enumerate(headings):
        next_start: int = (
            headings[i + 1].start if i + 1 < len(headings) else 10**12
        )
        if (
            heading.item == "1"
            and next_start - heading.start >= MIN_BUSINESS_CHARS
        ):
            return i
    return 0


def pick_body_headings(headings: list[Heading]) -> list[Heading]:
    """Keep one heading per Item: the first one in the body, in filing order.

    Some filings repeat "Item 1A" at the top of every page, so we take the
    first match, not the last. If a later Item turns up before the one we are
    looking for, that Item is missing from this filing and we skip it.
    """
    chosen: list[Heading] = []
    pos: int = 0
    for item in ITEM_TITLES:
        for j in range(pos, len(headings)):
            if ITEM_RANK[headings[j].item] > ITEM_RANK[item]:
                break  # a later Item came first: this Item is missing
            if headings[j].item == item:
                chosen.append(headings[j])
                pos = j + 1
                break
    return chosen
