from functools import cache
from typing import TypedDict, cast

import polars as pl

from sec_10k_rag.common.common import with_progress
from sec_10k_rag.common.db_config import DbConnInfo
from sec_10k_rag.common.llm_config import (
    # LLM_API_KEY,
    # LLM_BASE_URL,
    ask_llm,
    get_llm,
    # llm_client,
)
from sec_10k_rag.step_07_search_quality.config import COMPANY_NAMES
from sec_10k_rag.step_07_search_quality.lib.db import load_chunks_text_from_db
from sec_10k_rag.step_07_search_quality.lib.questions import with_prompt
from sec_10k_rag.step_08_mcp_server.lib.config import (
    NO_ANSWER,
    AnswerInstructions,
)
from sec_10k_rag.step_08_mcp_server.lib.extract_attributes import (
    extract_filing_attributes,
    validate_filing_attributes,
)
from sec_10k_rag.step_08_mcp_server.lib.search_filings import (
    retrieve_top_chunks,
)

REPLY_SCHEMA = pl.Struct({"answer": pl.String, "sources": pl.List(pl.Int64)})


class Citation(TypedDict):
    section_id: str
    item: str
    title: str
    source_url: str


class Answer(TypedDict):
    answer: str
    citations: list[Citation]


@cache
def available_filings(db: DbConnInfo, table: str) -> pl.DataFrame:
    return (
        load_chunks_text_from_db(db, table)
        .select("ticker", "fiscal_year")
        .unique()
    )


def build_passages(
    top_chunks: pl.DataFrame, ticker: str, fiscal_year: int
) -> str:
    return (
        with_prompt(
            top_chunks.with_columns(
                pl.lit(ticker).alias("ticker"),
                pl.lit(fiscal_year).alias("fiscal_year"),
            ),
            COMPANY_NAMES,
        )
        .select(pl.format("[{}] {}", "rank", "prompt").str.join("\n\n"))
        .item()
    )


def read_reply(reply: str) -> pl.DataFrame:
    return (
        pl.DataFrame({"reply": [reply]})
        .select(pl.col("reply").str.json_decode(REPLY_SCHEMA))
        .unnest("reply")
    )


def to_answer(top_chunks: pl.DataFrame, llm_reply: pl.DataFrame) -> Answer:
    sources = llm_reply.get_column("sources").explode().drop_nulls()
    citations = (
        top_chunks.filter(pl.col("rank").is_in(sources.implode()))
        .select("section_id", "item", "title", "source_url")
        .unique("section_id", maintain_order=True)
    )
    answers = llm_reply.get_column("answer").drop_nulls()
    return Answer(
        answer=next(iter(answers), NO_ANSWER),
        citations=cast(list[Citation], citations.to_dicts()),
    )


def answer_question(question: str, instructions: AnswerInstructions) -> Answer:
    ticker, fiscal_year = with_progress(extract_filing_attributes)(question)
    checked = validate_filing_attributes(
        ticker,
        fiscal_year,
        available_filings(instructions.db, instructions.chunks_table),
    )
    if checked.error is True:
        return Answer(answer=checked.error_msg, citations=[])

    ticker, fiscal_year = checked.values
    top_chunks = with_progress(retrieve_top_chunks)(
        ticker, fiscal_year, question, instructions.search
    )

    reply = with_progress(ask_llm)(
        get_llm(instructions.llm_info.max_retries),
        instructions.llm_info.model_name,
        instructions.llm_info.temperature,
        instructions.prompt,
        f"Question: {question}\n\nPassages:\n"
        f"{build_passages(top_chunks, ticker, fiscal_year)}",
    )
    return to_answer(top_chunks, read_reply(reply))
