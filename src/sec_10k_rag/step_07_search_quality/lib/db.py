import polars as pl

from sec_10k_rag.common.db_config import DbConnInfo, connect
from sec_10k_rag.step_07_search_quality.config import CHUNK_COLUMNS


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
