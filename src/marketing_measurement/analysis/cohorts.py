"""Cohort calculations for compact aggregate retention observations."""

from __future__ import annotations

import pandas as pd


def add_retention_rate(cohorts: pd.DataFrame) -> pd.DataFrame:
    """Add retention numerator, denominator, and rate to cohort aggregates."""
    required = {"cohort_users", "retained_users"}
    missing = required.difference(cohorts.columns)
    if missing:
        raise ValueError(f"cohorts is missing required columns: {sorted(missing)}")
    result = cohorts.copy()
    result["retention_rate_numerator"] = result["retained_users"]
    result["retention_rate_denominator"] = result["cohort_users"]
    result["retention_rate"] = result["retained_users"] / result["cohort_users"].where(
        result["cohort_users"].ne(0)
    )
    return result
