import polars as pl

from sec_10k_rag.step_07_search_quality.config import ScoreSearchInstructions
from sec_10k_rag.step_07_search_quality.lib import (
    load_chunks_text_from_db,
    search_chunks,
    vectorize_questions,
)


def retrieve_top_chunks(
    ticker: str,
    fiscal_year: int,
    query: str,
    instructions: ScoreSearchInstructions,
) -> pl.DataFrame:
    question = pl.DataFrame(
        {"question": [query], "ticker": [ticker], "fiscal_year": [fiscal_year]}
    )
    question_vector_df = vectorize_questions(question)
    top_chunks = search_chunks(question_vector_df, instructions)
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
