from pathlib import Path

import polars as pl
import psycopg
from psycopg import sql

from sec_10k_rag.common.common import load_parquet


def replace_rows(conn: psycopg.Connection, df: pl.DataFrame, table: str) -> None:
    table_id = sql.Identifier(table)
    columns = sql.SQL(", ").join(map(sql.Identifier, df.columns))
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)")
    with conn.cursor() as cur:
        cur.execute(sql.SQL("TRUNCATE {}").format(table_id))
        with cur.copy(copy_sql.format(table_id, columns)) as copy:
            copy.write(df.write_csv())


def load_embedded_chunks(file_path: Path) -> pl.DataFrame:
    return load_parquet(file_path)


def convert_embedding_column_to_text(df: pl.DataFrame) -> pl.DataFrame:
    vector_text = pl.col("embedding").cast(pl.List(pl.String)).list.join(",")
    text_vector_df = df.with_columns(pl.format("[{}]", vector_text).alias("embedding"))
    return text_vector_df


# def store_embedded_chunks_to_db(file_path: Path) -> bool:
#     df = load_embedded_chunks(file_path)
#     vector_text = pl.col("embedding").cast(pl.List(pl.String)).list.join(",")
#     text_vector_df = df.select("embedding").with_columns(
#         pl.format("[{}]", vector_text).alias("embedding")
#     )
