import time
from pathlib import Path

import polars as pl


def write_to_parquet_file(df: pl.DataFrame, parquet_file_name: Path) -> None:
    """Delete existing facts file and write new facts."""
    if parquet_file_name.exists():
        parquet_file_name.unlink()
        print(f"Deleted existing facts file: {parquet_file_name}")

    t = time.perf_counter()
    print(f"Writing facts to {parquet_file_name}...")
    parquet_file_name.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_file_name)
    print(f"wrote {df.height} rows to {parquet_file_name} in {time.perf_counter() - t:.2f}s")


def load_ndjson(file_path: Path) -> pl.DataFrame:
    return pl.read_ndjson(file_path)


def load_parquet(file_path: Path) -> pl.DataFrame:
    return pl.read_parquet(file_path)
