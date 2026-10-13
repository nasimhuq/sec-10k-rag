import polars as pl


def report_results(df: pl.DataFrame) -> None:
    print(
        f"chunks over the token limit: {df['truncated'].sum()} of {df.height}"
    )
    print(df["n_tokens"].describe())
