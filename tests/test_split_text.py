"""Tests for splitting 10-K sections into chunks, on small hand-made sections."""

import datetime as dt

import polars as pl

from sec_10k_rag.split_text.lib import chunk_sections, drop_short_sections
from sec_10k_rag.split_text.run import META_COLUMNS

TARGET: int = 1000


def make_sections(texts: dict[str, str]) -> pl.DataFrame:
    """One sections.jsonl-like row per (section_id, text)."""
    return pl.DataFrame(
        [
            {
                "section_id": section_id,
                "ticker": section_id.split("-")[0],
                "cik": "0000000001",
                "fiscal_year": 2025,
                "item": "7",
                "title": "MD&A",
                "report_date": "2025-06-30",
                "source_url": "https://example.com/10k.htm",
                "n_chars": len(text),
                "text": text,
            }
            for section_id, text in texts.items()
        ]
    )


def chunk(texts: dict[str, str]) -> pl.DataFrame:
    return chunk_sections(make_sections(texts), target_chars=TARGET, meta_columns=META_COLUMNS)


def test_drop_short_sections_keeps_only_long_enough() -> None:
    df = make_sections({"A-item4": "Not applicable.", "A-item7": "x" * 200})
    assert drop_short_sections(df, min_chars=150)["section_id"].to_list() == ["A-item7"]


def test_short_section_is_one_chunk() -> None:
    chunks = chunk({"A-item7": "Line one.\nLine two."})
    assert chunks["chunk_index"].to_list() == [0]
    assert chunks["text"].to_list() == ["Line one.\nLine two."]


def test_lines_are_packed_by_start_position_and_never_cut() -> None:
    # Lines start at 0, 601, 902 (bucket 0) and 1403, 1804 (bucket 1)
    lines = ["a" * 600, "b" * 300, "c" * 500, "d" * 400, "e" * 700]
    chunks = chunk({"A-item7": "\n".join(lines)})
    assert chunks["text"].to_list() == ["\n".join(lines[:3]), "\n".join(lines[3:])]


def test_blank_and_whitespace_only_lines_are_dropped() -> None:
    chunks = chunk({"A-item7": "First.\n\n   \n\u00a0\nSecond.\n"})
    assert chunks["text"].to_list() == ["First.\nSecond."]


def test_rejoined_chunks_equal_original_text() -> None:
    text = "\n".join(f"Paragraph {i}. " + "word " * (i * 37 % 120) for i in range(200))
    chunks = chunk({"A-item7": text})
    assert chunks.height > 1
    assert "\n".join(chunks["text"].to_list()) == text


def test_chunk_index_restarts_per_section_and_keys_are_unique() -> None:
    long_text = "\n".join(["x" * 600] * 6)  # starts 0, 601, 1202, 1803, 2404, 3005 → 4 chunks
    chunks = chunk({"A-item7": long_text, "A-item8": "Short.", "B-item1": long_text})
    per_section = chunks.group_by("section_id", maintain_order=True).agg("chunk_index")
    assert per_section.rows() == [
        ("A-item7", [0, 1, 2, 3]),
        ("A-item8", [0]),
        ("B-item1", [0, 1, 2, 3]),
    ]
    assert chunks.select(pl.struct("section_id", "chunk_index").n_unique()).item() == chunks.height


def test_no_empty_chunks_and_metadata_is_kept() -> None:
    chunks = chunk({"MSFT-2025-item7": "\n".join(["y" * 400] * 10)})
    assert chunks.columns == ["chunk_index", "text", *META_COLUMNS]
    assert (chunks["text"].str.strip_chars() != "").all()
    assert chunks.null_count().sum_horizontal().item() == 0
    assert chunks["ticker"].unique().to_list() == ["MSFT"]
    assert chunks.schema["report_date"] == pl.Date
    assert chunks["report_date"].unique().to_list() == [dt.date(2025, 6, 30)]
