from dataclasses import replace

import polars as pl

from sec_10k_rag.step_07_search_quality.config import (
    ConfigType,
    ScoreSearchInstructions,
    get_config,
)
from sec_10k_rag.step_07_search_quality.lib import (
    load_chunks_text_from_db,
    search_chunks,
    vectorize_questions,
)


def search_filings(
    ticker: str, fiscal_year: int, query: str, top_k: int
) -> pl.DataFrame:

    instructions = get_config(ConfigType.SCORE_SEARCH).instructions
    if not isinstance(instructions, ScoreSearchInstructions):
        raise TypeError("expected ScoreSearchInstructions")
    question = pl.DataFrame(
        {"question": [query], "ticker": [ticker], "fiscal_year": [fiscal_year]}
    )
    question_vector_df = vectorize_questions(question)
    top_chunks = search_chunks(
        question_vector_df, replace(instructions, top_k=top_k)
    )
    chunks = load_chunks_text_from_db(
        instructions.db, instructions.chunks_table
    )
    return (
        top_chunks.join(chunks, on=["section_id", "chunk_index"])
        .sort("rank")
        .select(
            "rank",
            "section_id",
            "chunk_index",
            "item",
            "title",
            "source_url",
            "rerank_score",
            "text",
        )
    )
