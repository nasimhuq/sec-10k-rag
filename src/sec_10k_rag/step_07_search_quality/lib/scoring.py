import polars as pl


def rank_of_source(
    vectors: pl.DataFrame, neighbors: pl.DataFrame
) -> pl.DataFrame:
    return vectors.select(
        "question_id", "section_id", "chunk_index", "question"
    ).join(
        neighbors,
        on=["question_id", "section_id", "chunk_index"],
        how="left",
    )


def score(ranks: pl.DataFrame, ks: tuple[int, ...]) -> pl.DataFrame:
    return ranks.select(
        *[
            (pl.col("rank") <= k).fill_null(False).mean().alias(f"recall@{k}")
            for k in ks
        ],
        (1 / pl.col("rank")).fill_null(0).mean().alias("mrr"),
    )
