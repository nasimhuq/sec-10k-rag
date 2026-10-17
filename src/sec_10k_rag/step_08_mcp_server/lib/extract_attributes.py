import re

# from typing import Literal
import polars as pl

from sec_10k_rag.common.result import Failure, Result, Success
from sec_10k_rag.step_07_search_quality.config import COMPANY_NAMES

YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def find_ticker(question: str) -> str | None:
    return next(
        (
            ticker
            for ticker, name in COMPANY_NAMES.items()
            if re.search(rf"\b({ticker}|{name})\b", question, re.IGNORECASE)
        ),
        None,
    )


def find_fiscal_year(question: str) -> int | None:
    match = YEAR_PATTERN.search(question)
    return int(match.group(1)) if match else None


def extract_filing_attributes(question: str) -> tuple[str | None, int | None]:
    return find_ticker(question), find_fiscal_year(question)


def validate_filing_attributes(
    ticker: str | None, fiscal_year: int | None, filings: pl.DataFrame
) -> Result[tuple[str, int]]:
    if ticker is None:
        names = ", ".join(COMPANY_NAMES.values())
        return Failure(error_msg=f"Please name the company: {names}.")
    years = (
        filings.filter(pl.col("ticker") == ticker)
        .get_column("fiscal_year")
        .sort()
        .to_list()
    )
    if fiscal_year is None or fiscal_year not in years:
        name = COMPANY_NAMES[ticker]
        listed = ", ".join(str(year) for year in years)
        return Failure(error_msg=f"Please name a {name} fiscal year: {listed}.")
    return Success(values=(ticker, fiscal_year))
