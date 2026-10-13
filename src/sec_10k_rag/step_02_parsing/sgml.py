"""Read the full-submission .txt: all documents of a filing, joined in SGML."""

import re

from sec_10k_rag.step_02_parsing.models import SgmlDocument

DOCUMENT: re.Pattern[str] = re.compile(r"<DOCUMENT>(.*?)</DOCUMENT>", re.DOTALL)
TYPE: re.Pattern[str] = re.compile(r"<TYPE>([^\n<]+)")
TEXT: re.Pattern[str] = re.compile(r"<TEXT>(.*)</TEXT>", re.DOTALL)


def extract_10k_html(submission: str) -> str:
    """Full-submission text -> HTML of the 10-K only (no exhibits, no XBRL)."""
    for document in split_documents(submission):
        if document.doc_type == "10-K":
            # Inline XBRL filings wrap the HTML in <XBRL> ... </XBRL>
            return document.text.replace("<XBRL>", "").replace("</XBRL>", "")
    raise ValueError("no 10-K document in this submission")


def split_documents(submission: str) -> list[SgmlDocument]:
    """Every <DOCUMENT> block that has a <TYPE> and a <TEXT>."""
    return [
        document
        for block in DOCUMENT.findall(submission)
        if (document := to_document(block)) is not None
    ]


def to_document(block: str) -> SgmlDocument | None:
    """One <DOCUMENT> block -> its type and text, or None if one is missing."""
    type_match: re.Match[str] | None = TYPE.search(block)
    text_match: re.Match[str] | None = TEXT.search(block)
    if type_match is None or text_match is None:
        return None
    return SgmlDocument(
        doc_type=type_match.group(1).strip(), text=text_match.group(1)
    )
