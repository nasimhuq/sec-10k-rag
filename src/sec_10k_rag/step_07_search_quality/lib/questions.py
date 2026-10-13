from functools import partial

import polars as pl

from sec_10k_rag.common.llm_config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    ask_llm,
    llm_client,
)
from sec_10k_rag.step_07_search_quality.config import (
    QUESTION_PROMPT,
    REPLY_SCHEMA,
    LlmInfo,
)


def ask_for_question(llm: llm_client, llm_info: LlmInfo, prompt: str) -> str:
    reply = ask_llm(
        llm, llm_info.model_name, llm_info.temperature, QUESTION_PROMPT, prompt
    )
    return reply or '{"skip": true}'


def with_prompt(
    sample: pl.DataFrame, company_names: dict[str, str]
) -> pl.DataFrame:
    return sample.with_columns(
        pl.format(
            "Company: {}\nFiscal year: {}\nSection: Item {} {}\n\nText:\n{}",
            pl.col("ticker").replace_strict(company_names),
            "fiscal_year",
            "item",
            "title",
            "text",
        ).alias("prompt")
    )


def sample_chunks(chunks: pl.DataFrame, n: int, seed: int) -> pl.DataFrame:
    return (
        chunks.with_columns(
            pl.int_range(pl.len())
            .shuffle(seed=seed)
            .over("ticker")
            .alias("pick_order")
        )
        .sort("pick_order", "ticker")
        .head(n)
        .drop("pick_order")
    )


def generate_questions(
    sample: pl.DataFrame, llm_info: LlmInfo, company_names: dict[str, str]
) -> pl.DataFrame:
    prompted = with_prompt(sample, company_names)
    llm = llm_client(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        max_retries=llm_info.max_retries,
    )
    return (
        prompted.with_columns(
            pl.col("prompt")
            .map_elements(
                partial(ask_for_question, llm, llm_info), return_dtype=pl.String
            )
            .str.json_decode(REPLY_SCHEMA)
            .alias("parsed")
        )
        .unnest("parsed")
        .filter(
            pl.col("question").is_not_null()
            & pl.col("text").str.contains(pl.col("quote"), literal=True)
        )
        .select(
            "section_id",
            "chunk_index",
            "ticker",
            "fiscal_year",
            "item",
            "question",
            "answer",
            "quote",
        )
    )
