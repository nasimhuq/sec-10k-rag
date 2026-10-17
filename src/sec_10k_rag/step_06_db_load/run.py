from sec_10k_rag.common.db_config import PG_TABLE, connect, get_db_conn_info
from sec_10k_rag.step_06_db_load.config import get_config
from sec_10k_rag.step_06_db_load.libs import (
    convert_embedding_column_to_text,
    load_embedded_chunks,
    replace_rows,
)


def main() -> None:
    config = get_config()
    df = load_embedded_chunks(config.input_data_dir / "chunks_embedded.parquet")
    text_df = convert_embedding_column_to_text(df)
    with connect(get_db_conn_info()) as conn:
        replace_rows(conn, text_df, PG_TABLE)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        )
        row = conn.execute(
            "SELECT count(*), count(embedding) FROM chunks"
        ).fetchone()
        if row is None or row[0] != text_df.height or row[1] != text_df.height:
            raise ValueError(
                f"load check failed: {row=}, expected {text_df.height}"
            )
        print(f"loaded {row[0]} rows into chunks")


if __name__ == "__main__":
    main()
