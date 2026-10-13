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
    SearchMode,
    get_config,
)
from sec_10k_rag.step_07_search_quality.lib.db import (
    connect,
    load_chunks_text_from_db,
)
from sec_10k_rag.step_07_search_quality.lib.rerank import rerank


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
        rows,
        schema={"section_id": pl.String, "chunk_index": pl.Int64},
        orient="row",
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


def keyword_query(
    table_name: str, filter_columns: tuple[str, ...]
) -> sql.Composed:
    conditions = sql.SQL(" AND ").join(
        [
            *(
                sql.SQL("{} = %s").format(sql.Identifier(col))
                for col in filter_columns
            ),
            sql.SQL("text_search @@ q.query"),
        ]
    )
    return sql.SQL(
        "SELECT section_id, chunk_index FROM {} "
        "CROSS JOIN (SELECT replace(plainto_tsquery('english', %s)::text, "
        "'&', '|')::tsquery AS query) AS q "
        "WHERE {} ORDER BY ts_rank(text_search, q.query) DESC LIMIT %s"
    ).format(sql.Identifier(table_name), conditions)


def find_keyword_matches(
    questions: pl.DataFrame,
    db: DbConnInfo,
    table: str,
    top_k: int,
    filter_columns: tuple[str, ...],
) -> pl.DataFrame:
    query = keyword_query(table, filter_columns)
    search_args = questions.select("question_id", "question", *filter_columns)
    with connect(db) as conn:
        return pl.concat(
            [
                nearest_for_one(
                    conn, query, (question, *values, top_k)
                ).with_columns(
                    pl.lit(qid, dtype=pl.UInt32).alias("question_id")
                )
                for qid, question, *values in search_args.iter_rows()
            ]
        )


def fuse_ranks(
    vector_ranks: pl.DataFrame,
    keyword_ranks: pl.DataFrame,
    rrf_k: int,
    top_k: int,
) -> pl.DataFrame:
    return (
        pl.concat([vector_ranks, keyword_ranks])
        .group_by("question_id", "section_id", "chunk_index")
        .agg((1 / (rrf_k + pl.col("rank"))).sum().alias("rrf_score"))
        .sort(
            "question_id",
            "rrf_score",
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
    )


def search_chunks(
    vectors: pl.DataFrame, ins: ScoreSearchInstructions
) -> pl.DataFrame:
    if ins.search_mode is SearchMode.VECTOR:
        return find_nearest_neighbors(
            vectors, ins.db, ins.chunks_table, ins.top_k, ins.filter_columns
        )

    vector_ranks = find_nearest_neighbors(
        vectors, ins.db, ins.chunks_table, ins.candidate_k, ins.filter_columns
    )
    keyword_ranks = find_keyword_matches(
        vectors, ins.db, ins.chunks_table, ins.candidate_k, ins.filter_columns
    )
    if ins.search_mode is SearchMode.HYBRID:
        return fuse_ranks(vector_ranks, keyword_ranks, ins.rrf_k, ins.top_k)

    candidates = fuse_ranks(
        vector_ranks, keyword_ranks, ins.rrf_k, ins.rerank_k
    )
    chunks_text = load_chunks_text_from_db(ins.db, ins.chunks_table)
    return rerank(candidates, vectors, chunks_text, ins.rerank_model, ins.top_k)
