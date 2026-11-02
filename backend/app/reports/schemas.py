from datetime import date
from typing import Any

from pydantic import BaseModel


class Report(BaseModel):
    """Every report has the same shape, so the admin page renders them all the same way:

    summary     headline numbers (cards)
    breakdowns  small tables / chart data, e.g. {"by_user": [...], "by_day": [...]}
    columns     the main table's columns – also the CSV columns
    rows        the main table (newest first, at most `row_limit`)
    """

    report: str
    title: str
    from_date: date
    to_date: date
    filters: dict[str, Any]
    summary: dict[str, int]
    breakdowns: dict[str, list[dict[str, Any]]]
    columns: list[str]
    rows: list[dict[str, Any]]
    row_limit: int
