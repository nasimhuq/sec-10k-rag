import polars as pl
from sentence_transformers import SentenceTransformer

from sec_10k_rag.embedding.config import Config, EmbeddingInstructions


def vectorize(config: Config[None | EmbeddingInstructions], df: pl.DataFrame) -> pl.DataFrame:
    if config.instructions is None:
        raise ValueError("vectorize needs EmbeddingInstructions")

    model = SentenceTransformer(config.instructions.model_name)
    embeddings = model.encode(  # pyright: ignore[reportUnknownMemberType]
        df["text"].to_list(),
        batch_size=config.instructions.batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )

    return df.with_columns(pl.Series("embedding", embeddings))
