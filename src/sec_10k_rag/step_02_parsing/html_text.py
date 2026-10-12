"""Turn a 10-K HTML document into clean plain text, one block per line."""

import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# Tags that start a new line when the page is rendered
BLOCK_TAGS: list[str] = ["p", "div", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6"]
HIDDEN_STYLE: re.Pattern[str] = re.compile(r"display:\s*none", re.IGNORECASE)
# Page furniture repeated on every printed page
NOISE_LINE: re.Pattern[str] = re.compile(r"^(\d{1,3}|table of contents)$", re.IGNORECASE)


def html_to_text(html: str | bytes) -> str:
    """HTML of a 10-K -> plain text with one block (paragraph, table row) per line.

    BeautifulSoup edits its tree in place, so this function builds its own
    tree, edits it, and throws it away. Callers only see input -> output.
    """
    with warnings.catch_warnings():
        # 10-Ks are XHTML; the forgiving HTML parser reads them fine
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")

    # 1. Remove things a reader never sees
    for tag in soup.find_all(["script", "style", "ix:header"]):
        tag.decompose()
    for tag in soup.find_all(style=HIDDEN_STYLE):
        tag.decompose()

    # 2. Keep the layout: line breaks after blocks, " | " between table cells
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for cell in soup.find_all(["td", "th"]):
        cell.append(" | ")
    for block in soup.find_all(BLOCK_TAGS):
        block.append("\n")

    return clean_text((soup.body or soup).get_text())


def clean_text(raw: str) -> str:
    """Clean every line, then drop empty lines and page furniture."""
    lines: list[str] = [clean_line(line) for line in raw.splitlines()]
    return "\n".join(line for line in lines if line and not NOISE_LINE.match(line))


def clean_line(line: str) -> str:
    """Normalize spaces and table-cell separators in one line."""
    line = line.replace("\xa0", " ")  # non-breaking space (&nbsp;)
    line = re.sub(r"\s+", " ", line)  # runs of spaces and tabs -> one space
    line = re.sub(r"(\s*\|\s*)+", " | ", line)  # empty cells -> one separator
    return line.strip(" |")
