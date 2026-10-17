from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class Failure:
    error_msg: str
    error: Literal[True] = True


@dataclass(frozen=True, kw_only=True)
class Success[T]:
    values: T
    error: Literal[False] = False


type Result[T] = Failure | Success[T]
