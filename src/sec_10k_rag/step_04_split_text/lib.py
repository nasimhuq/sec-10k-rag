from pathlib import Path

import polars as pl


def load_ndjson(file_path: Path) -> pl.DataFrame:
    return pl.read_ndjson(file_path)


def drop_short_sections(df: pl.DataFrame, min_chars: int = 100) -> pl.DataFrame:
    if df.null_count().sum_horizontal().item() > 0:
        df = df.drop_nulls()
    return df.filter(pl.col("n_chars") >= min_chars)


def chunk_sections(
    df: pl.DataFrame, target_chars: int, meta_columns: list[str]
) -> pl.DataFrame:
    """Pack whole lines of each section into chunks of about target_chars."""
    other_meta: list[str] = [c for c in meta_columns if c != "section_id"]
    return (
        df.with_columns(pl.col("text").str.split("\n").alias("para"))
        .explode("para", empty_as_null=True)
        .filter(pl.col("para").str.strip_chars() != "")
        .with_columns(
            pl.col("para").str.len_chars().cast(pl.Int64).alias("para_len")
        )
        .with_columns(
            (
                (pl.col("para_len") + 1).cum_sum().over("section_id")
                - pl.col("para_len")
                - 1
            ).alias("para_start_pos")
        )
        .with_columns(
            (pl.col("para_start_pos") // target_chars).alias("bucket")
        )
        .group_by("section_id", "bucket", maintain_order=True)
        .agg(
            pl.col("para").str.join("\n").alias("text"),
            *[pl.col(c).first() for c in other_meta],
        )
        .with_columns(
            pl.int_range(pl.len()).over("section_id").alias("chunk_index")
        )
        .with_columns(pl.col("report_date").str.to_date())
        .select("chunk_index", "text", *meta_columns)
    )
