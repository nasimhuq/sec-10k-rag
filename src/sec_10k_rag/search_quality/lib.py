from functools import partial
from pathlib import Path

# from pathlib import Path
import polars as pl
import psycopg

# from groq import Groq
from psycopg import sql
from psycopg.rows import TupleRow

from sec_10k_rag.common.common import load_parquet
from sec_10k_rag.common.llm_config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    ask_llm,
    llm_client,
)
from sec_10k_rag.embedding.config import ConfigType as EmbeddingConfigType
from sec_10k_rag.embedding.config import get_config as get_embedding_config
from sec_10k_rag.embedding.vectorize import vectorize
from sec_10k_rag.search_quality.config import (
    CHUNK_COLUMNS,
    QUESTION_PROMPT,
    REPLY_SCHEMA,
    ConfigType,
    DbConnInfo,
    LlmInfo,
    ScoreSearchInstructions,
    get_config,
)


def connect(db: DbConnInfo) -> psycopg.Connection[TupleRow]:
    return psycopg.connect(
        host=db.host,
        port=db.port,
        dbname=db.dbname,
        user=db.user,
        password=db.password,
    )


def load_chunks_text_from_db(
    db_conn: DbConnInfo, table_name: str
) -> pl.DataFrame:
    # query = f"SELECT {CHUNK_COLUMNS} FROM {table_name} ORDER BY section_id, chunk_index"
    query = (
        f"SELECT {CHUNK_COLUMNS} FROM {table_name} "
        "ORDER BY section_id, chunk_index"
    )
    # query = f"SELECT {CHUNK_COLUMNS} FROM {table_name} ORDER BY section_id, chunk_index"
    with connect(db_conn) as conn:
        return pl.read_database(query, connection=conn)  # pyright: ignore[reportUnknownMemberType]


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


def ask_for_question(llm: llm_client, llm_info: LlmInfo, prompt: str) -> str:
    reply = ask_llm(
        llm, llm_info.model_name, llm_info.temperature, QUESTION_PROMPT, prompt
    )
    return reply or '{"skip": true}'


# def ask_for_question(llm: llm_client, llm_info: LlmInfo, prompt: str) -> str:
#     reply = llm.chat.completions.create(
#         model=llm_info.model_name,
#         temperature=llm_info.temperature,
#         response_format={"type": "json_object"},
#         messages=[
#             {"role": "system", "content": QUESTION_PROMPT},
#             {"role": "user", "content": prompt},
#         ],
#     )
#     return reply.choices[0].message.content or '{"skip": true}'


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


def get_question_vectors(questions_path: Path) -> pl.DataFrame:
    config = get_config(ConfigType.SCORE_SEARCH)
    instructions = config.instructions

    if not isinstance(instructions, ScoreSearchInstructions):
        raise TypeError("expected ScoreSearchInstructions")

    embedding_config = get_embedding_config(EmbeddingConfigType.VECTORIZE)

    questions = load_parquet(questions_path).with_row_index("question_id")

    queries = questions.with_columns(
        (pl.lit(instructions.query_prefix) + pl.col("question")).alias("query")
    )
    return vectorize(embedding_config, queries, text_column_name="query")


def nearest_for_one(
    conn: psycopg.Connection[TupleRow],
    query: sql.Composed,
    vector: str,
    top_k: int,
) -> pl.DataFrame:
    rows = conn.execute(query, (vector, top_k)).fetchall()
    return pl.DataFrame(
        rows, schema=["section_id", "chunk_index"], orient="row"
    ).with_row_index("rank", offset=1)


def find_nearest_neighbors(
    vectors: pl.DataFrame, db: DbConnInfo, table: str, top_k: int
) -> pl.DataFrame:
    query = sql.SQL(
        "SELECT section_id, chunk_index FROM {} "
        "ORDER BY embedding <=> %s::vector LIMIT %s"
    ).format(sql.Identifier(table))
    as_text = vectors.select(
        "question_id",
        pl.format(
            "[{}]",
            pl.col("embedding").cast(pl.List(pl.String)).list.join(","),
        ).alias("vector"),
    )
    with connect(db) as conn:
        return pl.concat(
            [
                nearest_for_one(conn, query, vector, top_k).with_columns(
                    pl.lit(qid, dtype=pl.UInt32).alias("question_id")
                )
                for qid, vector in as_text.iter_rows()
            ]
        )


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
