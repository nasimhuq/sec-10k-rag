from pathlib import Path

import polars as pl
import psycopg
from psycopg import sql
from psycopg.rows import TupleRow

from sec_10k_rag.common.common import load_parquet
from sec_10k_rag.step_05_embedding.config import (
    ConfigType as EmbeddingConfigType,
)
from sec_10k_rag.step_05_embedding.config import (
    get_config as get_embedding_config,
)
from sec_10k_rag.step_05_embedding.vectorize import vectorize
from sec_10k_rag.step_07_search_quality.config import (
    ConfigType,
    DbConnInfo,
    ScoreSearchInstructions,
    get_config,
)
from sec_10k_rag.step_07_search_quality.lib.db import connect


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
    search_args: tuple[object, ...],
) -> pl.DataFrame:
    rows = conn.execute(query, search_args).fetchall()
    return pl.DataFrame(
        rows, schema=["section_id", "chunk_index"], orient="row"
    ).with_row_index("rank", offset=1)


def find_nearest_neighbors(
    vectors: pl.DataFrame,
    db: DbConnInfo,
    table: str,
    top_k: int,
    filter_columns: tuple[str, ...],
) -> pl.DataFrame:
    query = search_query(table, filter_columns)
    as_text = vectors.select(
        "question_id",
        *filter_columns,
        pl.format(
            "[{}]",
            pl.col("embedding").cast(pl.List(pl.String)).list.join(","),
        ).alias("vector"),
    )
    with connect(db) as conn:
        conn.execute("SET hnsw.iterative_scan = strict_order")
        return pl.concat(
            [
                nearest_for_one(
                    conn, query, (*values, vector, top_k)
                ).with_columns(
                    pl.lit(qid, dtype=pl.UInt32).alias("question_id")
                )
                for qid, *values, vector in as_text.iter_rows()
            ]
        )


def search_query(
    table_name: str, filter_columns: tuple[str, ...]
) -> sql.Composed:
    conditions = sql.SQL(" AND ").join(
        sql.SQL("{} = %s").format(sql.Identifier(col)) for col in filter_columns
    )
    where = sql.SQL("WHERE ") + conditions if filter_columns else sql.SQL("")
    return sql.SQL(
        "SELECT section_id, chunk_index FROM {} {} "
        "ORDER BY embedding <=> %s::vector LIMIT %s"
    ).format(sql.Identifier(table_name), where)
