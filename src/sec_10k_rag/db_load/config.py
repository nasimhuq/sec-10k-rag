from collections.abc import Callable

# from dataclasses import dataclass
from enum import StrEnum, auto

from sec_10k_rag.common.config import Config
from sec_10k_rag.embedding.config import EMBEDDING_DIR

# from sec_10k_rag.embedding.config import get_load_chunks_config


class ConfigType(StrEnum):
    LOAD_EMBEDDED_CHUNKS = auto()  # value "load_chunks"


# EMBEDDING_DIR = PROCESSED_DIR / "embedding"


def get_load_embedded_chunks_config() -> Config[None]:
    return Config(
        input_data_dir=EMBEDDING_DIR,
        processed_data_dir=EMBEDDING_DIR,
    )


CONFIG_FACTORIES: dict[ConfigType, Callable[[], Config[None]]] = {
    ConfigType.LOAD_EMBEDDED_CHUNKS: get_load_embedded_chunks_config,
}


def get_config(
    config_type: ConfigType | None = None,
) -> Config[None]:
    if config_type is None:
        return get_load_embedded_chunks_config()
    return CONFIG_FACTORIES[config_type]()
