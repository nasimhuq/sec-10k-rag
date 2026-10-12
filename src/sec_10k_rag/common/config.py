from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
INPUT_DATA_DIR = ROOT_DIR / "data/raw"
PROCESSED_DIR = ROOT_DIR / "data/processed"
LOG_DIR = ROOT_DIR / "logs"
TEMP_DIR = ROOT_DIR / "temp"
LLM_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True, kw_only=True)
class Config[Instructions]:
    command: str = "run"
    root_dir: Path = ROOT_DIR
    input_data_dir: Path = INPUT_DATA_DIR
    processed_data_dir: Path = PROCESSED_DIR
    log_dir: Path = LOG_DIR
    temp_dir: Path = TEMP_DIR
    instructions: Instructions | None = None
