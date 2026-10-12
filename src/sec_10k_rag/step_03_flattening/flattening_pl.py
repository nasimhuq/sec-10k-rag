import time
from pathlib import Path

import polars as pl

from sec_10k_rag.common.common import write_to_parquet_file
from sec_10k_rag.step_03_flattening.flatten_pl import apply_map, convert, flatten

RAW_DIR = Path("data/raw")
SCRIPT_DIR = Path(__file__).parent
OUT_FILE = Path("data/processed/facts.parquet")


def load_config_map() -> pl.DataFrame:
    """Load the configuration mapping from a JSON file."""
    config_path = SCRIPT_DIR / "flattening_map.json"
    print(f"Loading configuration mapping from: {config_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    return pl.read_json(config_path).select("simple_map").unnest("simple_map")


def main() -> None:
    cfg_df = load_config_map()
    print(f"Loaded configuration mapping with {cfg_df.height} rows")
    print(cfg_df)
    frames: list[pl.DataFrame] = []
    for p in sorted(Path("data/raw").glob("*/companyfacts.json")):
        t = time.perf_counter()
        src_df = pl.read_json(p)
        out_df = convert(apply_map(flatten(src_df), cfg_df), cfg_df)
        frames.append(out_df.with_columns(pl.lit(p.parent.name).alias("ticker")))
        print(p.parent.name, out_df.height, f"{time.perf_counter() - t:.2f}s")

    facts = pl.concat(frames, how="diagonal_relaxed")
    write_to_parquet_file(facts, OUT_FILE)
    # write_facts(facts)


if __name__ == "__main__":
    main()
