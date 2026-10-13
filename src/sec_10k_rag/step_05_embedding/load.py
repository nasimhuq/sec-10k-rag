import polars as pl

from sec_10k_rag.common.common import load_parquet
from sec_10k_rag.step_05_embedding.config import Config, EmbeddingInstructions


def load_chunks(
    config: Config[None | EmbeddingInstructions], file_name: str
) -> pl.DataFrame:
    file_path = config.root_dir / config.input_data_dir / file_name

    if not file_path.exists():
        raise FileNotFoundError(f"Input data file does not exist: {file_path}")

    return load_parquet(file_path)
