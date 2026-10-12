import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from itertools import cycle
from pathlib import Path

import polars as pl

from sec_10k_rag.common.config import DB_SERVICE, ROOT_DIR

# from sentence_transformers import SentenceTransformer

# from sec_10k_rag.common.config import Config

SPINNER_FRAMES = "⠀⠄⠆⠇⠇⠗⠷⠿"
SPINNER_INTERVAL_S = 0.1
CLEAR_TO_EOL = "\033[K"
PROGRESS_WIDTH = 40
PROGRESS_INDENT = " "
DURATION_WIDTH = 7  # fits 9999.99
_spinner_lock = threading.Lock()
_print_lock = threading.Lock()


@dataclass
class _RunningCall:
    name: str
    depth: int
    start: float
    has_header: bool = False


_progress_stack: list[_RunningCall] = []


def start_db(service: str = DB_SERVICE) -> None:
    subprocess.run(
        ["docker", "compose", "up", "--detach", "--wait", service],
        cwd=ROOT_DIR,
        check=True,
    )


def write_to_parquet_file(df: pl.DataFrame, parquet_file_name: Path) -> None:
    """Delete existing facts file and write new facts."""
    if parquet_file_name.exists():
        parquet_file_name.unlink()
        print(f"Deleted existing facts file: {parquet_file_name}")

    t = time.perf_counter()
    print(f"Writing facts to {parquet_file_name}...")
    parquet_file_name.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(parquet_file_name)
    print(
        f"wrote {df.height} rows to {parquet_file_name} in {time.perf_counter() - t:.2f}s"
    )


def _emit(text: str, end: str = "\n") -> None:
    """Write text over whatever the spinner last drew on the current line."""
    clear = CLEAR_TO_EOL if sys.stdout.isatty() else ""
    with _print_lock:
        sys.stdout.write(f"{clear}{text}{end}")
        sys.stdout.flush()


def _spin(stop: threading.Event, label: Callable[[], str]) -> None:
    for frame in cycle(SPINNER_FRAMES):
        if stop.wait(SPINNER_INTERVAL_S):
            return
        _emit(f"{label()} {frame}", end="\r")


@contextmanager
def spinner(label: Callable[[], str]) -> Generator[None]:
    """Animate a spinner after the current label until the block exits.

    Does nothing when stdout is not a terminal or a spinner is already running.
    """
    if not sys.stdout.isatty() or not _spinner_lock.acquire(blocking=False):
        yield
        return
    stop = threading.Event()
    thread = threading.Thread(target=_spin, args=(stop, label), daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        _emit("", end="")
        _spinner_lock.release()


def dotted_label(name: str, depth: int) -> str:
    label = f"{PROGRESS_INDENT * depth}{name}..."
    return label.ljust(PROGRESS_WIDTH, ".")


def running_line(call: _RunningCall) -> str:
    seconds = int(time.perf_counter() - call.start)
    return (
        f"{dotted_label(call.name, call.depth)} [{seconds:{DURATION_WIDTH}d}s]"
    )


def with_progress[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Wrap fn so each call reports `name........ [1.23s]` when it finishes.

    While a call runs, its line shows the elapsed seconds and a spinner.
    Nested calls are indented under a header line for their caller, whose own
    total comes after them.
    """

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        depth = len(_progress_stack)
        if depth and not _progress_stack[-1].has_header:
            parent = _progress_stack[-1]
            parent.has_header = True
            _emit(f"{PROGRESS_INDENT * (depth - 1)}{parent.name}")
        start = time.perf_counter()
        _progress_stack.append(_RunningCall(fn.__name__, depth, start))
        try:
            with spinner(lambda: running_line(_progress_stack[-1])):
                return fn(*args, **kwargs)
        finally:
            seconds = time.perf_counter() - start
            _progress_stack.pop()
            _emit(
                f"{dotted_label(fn.__name__, depth)} "
                f"[{seconds:{DURATION_WIDTH}.2f}s]"
            )

    return wrapper


def load_ndjson(file_path: Path) -> pl.DataFrame:
    return pl.read_ndjson(file_path)


def load_parquet(file_path: Path) -> pl.DataFrame:
    return pl.read_parquet(file_path)
