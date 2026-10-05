import re

import polars as pl
import polars.selectors as cs

ZERO_PAD = re.compile(r"0(\d+)d")
LEVEL_PREFIX = "__col"
NODE = "__node"


def to_expr(col: str, spec: dict[str, str | None]) -> pl.Expr:
    """One conversion rule from the map becomes one Polars expression."""
    expr = pl.col(col)
    if spec.get("type") == "date":
        return expr.str.to_date()
    if spec.get("type") == "float":
        return expr.cast(pl.Float64)
    if (fmt := spec.get("format")) and (pad := ZERO_PAD.fullmatch(fmt)):
        return expr.cast(pl.String).str.zfill(int(pad[1]))
    return expr


def convert(df: pl.DataFrame, cfg: pl.DataFrame) -> pl.DataFrame:
    """Apply every rule in `conversion` in one with_columns call."""
    return df.with_columns([to_expr(col, spec) for col, spec in cfg["conversion"][0].items()])


def apply_map(df: pl.DataFrame, cfg: pl.DataFrame) -> pl.DataFrame:
    """Rename level columns, drop leftover levels and listed columns, keep allowed rows."""
    df = df.rename(cfg["rename_columns"][0], strict=False).drop(
        cs.starts_with(LEVEL_PREFIX), *cfg["drop_columns"][0], strict=False
    )
    for col, values in cfg["allowed_rows"][0].items():
        df = df.filter(pl.col(col).is_in(values))
    return df


def flatten(df: pl.DataFrame) -> pl.DataFrame:
    """Each JSON level's keys become a __colN column; each item of the first list is a row."""
    depth = 1
    while df.select(cs.nested()).width > 0:
        df = df.unpivot(
            cs.nested(), index=~cs.nested(), variable_name=f"{LEVEL_PREFIX}{depth}", value_name=NODE
        ).drop_nulls(NODE)
        if df.schema[NODE] == pl.List:
            df = df.explode(NODE, empty_as_null=False).unnest(NODE)
            return df.unnest(cs.struct(), separator="_")  # sub -> sub_final, sub_next
        df = df.unnest(NODE)
        depth += 1
    return df
