import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

import polars as pl
from dotenv import load_dotenv

from sec_10k_rag.common.config import (
    LLM_BASE_URL,
    PROCESSED_DIR,
    ROOT_DIR,
    Config,
)

SEARCH_QUALITY_DIR = PROCESSED_DIR / "search_quality"
QUESTIONS_FILE = "questions.parquet"
SCORES_FILE = "scores.parquet"
PG_TABLE = "chunks"
COMPANY_NAMES: dict[str, str] = {
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "TSLA": "Tesla",
}

CHUNK_COLUMNS = (
    "section_id, chunk_index, ticker, fiscal_year, item, title, text"
)
QUESTION_PROMPT = """Write one question that the text below answers.
Use your own words, not the text's. Name the company and fiscal year.
"quote" must be copied exactly from the text, 5-15 words.
If the text has no clear fact, return {"skip": true}.
Otherwise return JSON only: 
{"question": "...", "answer": "...", "quote": "..."}"""

REPLY_SCHEMA = pl.Struct(
    {"question": pl.String, "answer": pl.String, "quote": pl.String}
)
LLM_MODEL_NAME = "openai/gpt-oss-120b"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
FILTER_COLUMNS = ("ticker", "fiscal_year")
RERANK_MODEL = "BAAI/bge-reranker-base"


@dataclass(frozen=True, kw_only=True)
class DbConnInfo:
    port: str
    dbname: str
    user: str
    password: str = field(repr=False)
    host: str = "127.0.0.1"


@dataclass(frozen=True, kw_only=True)
class LlmInfo:
    model_name: str
    temperature: float
    max_retries: int = 10
    base_url: str = LLM_BASE_URL


@dataclass(frozen=True, kw_only=True)
class GenerateQuestionsInstructions:
    db: DbConnInfo
    llm_info: LlmInfo
    sample_size: int
    seed: int
    output_file_name: str = QUESTIONS_FILE
    chunks_table: str = PG_TABLE
    company_names: dict[str, str] = field(
        default_factory=lambda: dict(COMPANY_NAMES)
    )


class SearchMode(StrEnum):
    VECTOR = "vector"  # 5b (baseline also sets filter_columns=())
    HYBRID = "hybrid"  # 5c: vector + keyword, RRF
    RERANK = "rerank"  # 5d: 5c + CrossEncoder


@dataclass(frozen=True, kw_only=True)
class ScoreSearchInstructions:
    db: DbConnInfo
    top_k: int  # 10
    query_prefix: str = QUERY_PREFIX
    input_file_name: str = QUESTIONS_FILE
    output_file_name: str = SCORES_FILE
    chunks_table: str = PG_TABLE
    recall_ks: tuple[int, ...] = (1, 3, 5, 10)
    filter_columns: tuple[str, ...] = FILTER_COLUMNS
    search_mode: SearchMode = SearchMode.RERANK
    candidate_k: int = 30  # rows taken from each search before fusing
    rrf_k: int = 60
    rerank_k: int = 30  # fused rows sent to the reranker
    rerank_model: str = RERANK_MODEL


class ConfigType(StrEnum):
    GENERATE_QUESTIONS = "generate_questions"
    SCORE_SEARCH = "score_search"


def get_db_conn_info() -> DbConnInfo:
    load_dotenv(ROOT_DIR / ".env")
    return DbConnInfo(
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
    )


def get_generate_questions_config() -> Config[GenerateQuestionsInstructions]:
    return Config(
        input_data_dir=SEARCH_QUALITY_DIR,
        processed_data_dir=SEARCH_QUALITY_DIR,
        instructions=GenerateQuestionsInstructions(
            db=get_db_conn_info(),
            llm_info=LlmInfo(
                model_name=LLM_MODEL_NAME,
                temperature=0.0,
            ),
            sample_size=50,
            seed=42,
            company_names=COMPANY_NAMES,
        ),
    )


def get_score_search_config() -> Config[ScoreSearchInstructions]:
    return Config(
        input_data_dir=SEARCH_QUALITY_DIR,
        processed_data_dir=SEARCH_QUALITY_DIR,
        instructions=ScoreSearchInstructions(
            db=get_db_conn_info(),
            top_k=10,
        ),
    )


CONFIG_FACTORIES: dict[
    ConfigType,
    Callable[
        [],
        Config[None | GenerateQuestionsInstructions | ScoreSearchInstructions],
    ],
] = {
    ConfigType.GENERATE_QUESTIONS: get_generate_questions_config,
    ConfigType.SCORE_SEARCH: get_score_search_config,
}


def get_config(
    config_type: ConfigType,
) -> Config[GenerateQuestionsInstructions | ScoreSearchInstructions | None]:
    return CONFIG_FACTORIES[config_type]()


def get_llm_api_key() -> str:
    load_dotenv(ROOT_DIR / ".env")
    return os.environ["OPEN_ROUTER_API_KEY"]
