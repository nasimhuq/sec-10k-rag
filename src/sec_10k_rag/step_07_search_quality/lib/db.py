import polars as pl
import psycopg
from psycopg.rows import TupleRow

from sec_10k_rag.step_07_search_quality.config import (
    CHUNK_COLUMNS,
    DbConnInfo,
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
    query = (
        f"SELECT {CHUNK_COLUMNS} FROM {table_name} "
        "ORDER BY section_id, chunk_index"
    )
    with connect(db_conn) as conn:
        return pl.read_database(  # pyright: ignore[reportUnknownMemberType]
            query,
            connection=conn,
            schema_overrides={"chunk_index": pl.Int64},
        )
