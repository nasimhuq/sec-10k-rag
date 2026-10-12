import polars as pl
from sentence_transformers import SentenceTransformer

from sec_10k_rag.common.config import Config
from sec_10k_rag.step_05_embedding.config import EmbeddingInstructions


def tokenize(config: Config[None | EmbeddingInstructions], df: pl.DataFrame) -> pl.DataFrame:
    if config.instructions is None:
        raise ValueError("tokenize needs EmbeddingInstructions")

    model = SentenceTransformer(config.instructions.model_name)
    input_ids = model.tokenizer(df["text"].to_list())["input_ids"]

    return (
        df.select("section_id", "chunk_index")
        .with_columns(pl.Series("n_tokens", input_ids).list.len())
        .with_columns(truncated=pl.col("n_tokens") > model.max_seq_length)
    )
