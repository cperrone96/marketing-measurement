"""Funnel rates computed from compact, aggregate session counts."""

from __future__ import annotations

import pandas as pd


def funnel_rates(counts: pd.DataFrame) -> pd.DataFrame:
    """Add sequential descriptive rates without filling unmeasured values with zero."""
    stages = ["views", "engaged_sessions", "add_to_carts", "checkouts", "purchases"]
    missing = set(stages).difference(counts.columns)
    if missing:
        raise ValueError(f"counts is missing funnel stages: {sorted(missing)}")
    result = counts.copy()
    for numerator, denominator in zip(stages[1:], stages[:-1], strict=True):
        result[f"{numerator}_rate"] = result[numerator] / result[denominator].where(
            result[denominator].ne(0)
        )
        result[f"{numerator}_numerator"] = result[numerator]
        result[f"{numerator}_denominator"] = result[denominator]
    return result
