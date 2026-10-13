# How `pairs` is built in rerank()
#
# The CrossEncoder needs the question text and the chunk text side by side,
# so we build one row per (question, candidate chunk) with both texts.
# Each join adds columns by matching keys, like SQL INNER JOIN ... USING.
# (Section ids below are made up, to show the shape.)
#
# Start, `candidates` (fused top 30 per question, ids only):
#   question_id | section_id   | chunk_index | rrf_score | rank
#   0           | TSLA_2024_7  | 12          | 0.032     | 1
#   0           | TSLA_2024_1A | 3           | 0.016     | 2
#
# Join 1: add the question text, matched on question_id
#   questions.select("question_id", "question"):
#   question_id | question
#   0           | What was Tesla's revenue in fiscal 2024?
#   -> every candidate row of question 0 gets that question:
#   question_id | section_id   | chunk_index | rrf_score | rank | question
#   0           | TSLA_2024_7  | 12          | 0.032     | 1    | What was Tesla's revenue in fiscal 2024?  # noqa: E501
#   0           | TSLA_2024_1A | 3           | 0.016     | 2    | What was Tesla's revenue in fiscal 2024?  # noqa: E501
#
# Join 2: add the chunk text, matched on section_id + chunk_index
# (together they identify one chunk, like the Postgres primary key)
#   chunks_text.select("section_id", "chunk_index", "text"):
#   section_id   | chunk_index | text
#   TSLA_2024_7  | 12          | Total revenues were $97.7 billion...
#   TSLA_2024_1A | 3           | We may be impacted by...
#
# Result, `pairs`:
#   question_id | section_id   | chunk_index | rrf_score | rank | question                                 | text  # noqa: E501
#   0           | TSLA_2024_7  | 12          | 0.032     | 1    | What was Tesla's revenue in fiscal 2024? | Total revenues were $97.7 billion...  # noqa: E501
#   0           | TSLA_2024_1A | 3           | 0.016     | 2    | What was Tesla's revenue in fiscal 2024? | We may be impacted by...  # noqa: E501
#
# pairs.select("question", "text").rows() turns those two columns into
# the list of (question, text) tuples that model.predict() scores:
#   [("What was Tesla's revenue in fiscal 2024?", "Total revenues were $97.7 billion..."),  # noqa: E501
#    ("What was Tesla's revenue in fiscal 2024?", "We may be impacted by...")]
#
# Why .select(...) before each join: keep only the columns we need.
# The questions frame also has its own section_id / chunk_index (the
# source chunk); they would clash with the candidate's columns.

import polars as pl
from sentence_transformers import CrossEncoder


def rerank(
    candidates: pl.DataFrame,
    questions: pl.DataFrame,
    chunks_text: pl.DataFrame,
    model_name: str,
    top_k: int,
) -> pl.DataFrame:
    pairs = candidates.join(
        questions.select("question_id", "question"), on="question_id"
    ).join(
        chunks_text.select("section_id", "chunk_index", "text"),
        on=["section_id", "chunk_index"],
    )
    model = CrossEncoder(model_name)
    scores = model.predict(  # pyright: ignore[reportUnknownMemberType]
        pairs.select("question", "text").rows()
    )
    return (
        pairs.with_columns(pl.Series("rerank_score", scores))
        .sort(
            "question_id",
            "rerank_score",
            "section_id",
            "chunk_index",
            descending=[False, True, False, False],
        )
        .with_columns(
            pl.int_range(1, pl.len() + 1, dtype=pl.UInt32)
            .over("question_id")
            .alias("rank")
        )
        .filter(pl.col("rank") <= top_k)
        .select(
            "question_id", "section_id", "chunk_index", "rank", "rerank_score"
        )
    )
