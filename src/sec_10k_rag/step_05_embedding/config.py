from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, auto

from sec_10k_rag.common.config import PROCESSED_DIR, Config


class ConfigType(StrEnum):
    LOAD_CHUNKS = auto()  # value "load_chunks"
    TOKENIZE = auto()
    VECTORIZE = auto()


EMBEDDING_DIR = PROCESSED_DIR / "embedding"


@dataclass(frozen=True)
class EmbeddingInstructions:
    model_name: str = "BAAI/bge-small-en-v1.5"
    batch_size: int = 64


def get_default_config() -> Config[EmbeddingInstructions]:
    return Config(
        input_data_dir=EMBEDDING_DIR,
        processed_data_dir=EMBEDDING_DIR,
        instructions=EmbeddingInstructions(),
    )


def get_load_chunks_config() -> Config[None]:
    return Config(
        input_data_dir=PROCESSED_DIR,
        processed_data_dir=EMBEDDING_DIR,
    )


def get_tokenize_config() -> Config[EmbeddingInstructions]:
    return Config(
        input_data_dir=EMBEDDING_DIR,
        processed_data_dir=EMBEDDING_DIR,
        instructions=EmbeddingInstructions(),
    )


CONFIG_FACTORIES: dict[
    ConfigType, Callable[[], Config[None | EmbeddingInstructions]]
] = {
    ConfigType.LOAD_CHUNKS: get_load_chunks_config,
    ConfigType.TOKENIZE: get_tokenize_config,
    ConfigType.VECTORIZE: get_default_config,
}


def get_config(
    config_type: ConfigType | None = None,
) -> Config[EmbeddingInstructions | None]:
    if config_type is None:
        return get_default_config()
    return CONFIG_FACTORIES[config_type]()
