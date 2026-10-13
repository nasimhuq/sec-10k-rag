from pathlib import Path

from sec_10k_rag.common.common import write_to_parquet_file
from sec_10k_rag.step_04_split_text.lib import (
    chunk_sections,
    drop_short_sections,
    load_ndjson,
)

TARGET_CHARS = 1000
MIN_CHARS = 150
META_COLUMNS = [
    "section_id",
    "ticker",
    "cik",
    "fiscal_year",
    "item",
    "title",
    "report_date",
    "source_url",
]
DATA_DIR = Path("data/processed")


def main() -> None:

    file_path = DATA_DIR / "sections.jsonl"
    df = drop_short_sections(load_ndjson(file_path), MIN_CHARS)
    chunked_df = chunk_sections(
        df, target_chars=TARGET_CHARS, meta_columns=META_COLUMNS
    )
    print(df.height)
    parquet_file_dir = DATA_DIR / "chunks.parquet"
    write_to_parquet_file(chunked_df, parquet_file_dir)


if __name__ == "__main__":
    main()
