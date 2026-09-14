"""Deterministic descriptive attribution for compact, non-identifying paths."""

from __future__ import annotations

from typing import Literal

import pandas as pd

AttributionModel = Literal["first_touch", "last_touch", "linear", "time_decay"]
_MODELS = frozenset({"first_touch", "last_touch", "linear", "time_decay"})
_INTERPRETATION = "descriptive attribution; not causal"


def attribution_credits(paths: pd.DataFrame, model: AttributionModel) -> pd.DataFrame:
    """Allocate one unit of descriptive credit per conversion across touches.

    ``paths`` must contain a non-identifying conversion label, channel, and either
    ``touch_number`` or ``touch_timestamp``.  Time decay uses a half-life of one
    ordered touch; it is an accounting convention, not evidence of causality.
    """
    if model not in _MODELS:
        raise ValueError(f"Unsupported attribution model: {model}")
    required = {"conversion_id", "channel"}
    missing = required.difference(paths.columns)
    if missing:
        raise ValueError(f"paths is missing required columns: {sorted(missing)}")
    if "touch_number" not in paths.columns and "touch_timestamp" not in paths.columns:
        raise ValueError("paths must include touch_number or touch_timestamp")

    order_columns = ["conversion_id"]
    order_columns.append("touch_timestamp" if "touch_timestamp" in paths.columns else "touch_number")
    ordered = paths.copy().sort_values(order_columns, kind="stable").reset_index(drop=True)
    if ordered["conversion_id"].isna().any() or ordered["channel"].isna().any():
        raise ValueError("conversion_id and channel cannot be missing")

    ordered["touch_position"] = ordered.groupby("conversion_id", sort=False).cumcount()
    ordered["touches_in_conversion"] = ordered.groupby("conversion_id", sort=False)[
        "conversion_id"
    ].transform("size")
    ordered["credit"] = _credits_for_model(ordered, model)
    ordered["interpretation"] = _INTERPRETATION

    if not _credit_sums_to_one(ordered):
        raise RuntimeError("Attribution credits must sum to one per conversion")
    return ordered


def _credits_for_model(frame: pd.DataFrame, model: AttributionModel) -> pd.Series:
    if model == "first_touch":
        return (frame["touch_position"] == 0).astype(float)
    if model == "last_touch":
        return (
            frame["touch_position"] == frame["touches_in_conversion"] - 1
        ).astype(float)
    if model == "linear":
        return 1.0 / frame["touches_in_conversion"]

    raw_weight = 0.5 ** (frame["touches_in_conversion"] - 1 - frame["touch_position"])
    return raw_weight / raw_weight.groupby(frame["conversion_id"], sort=False).transform("sum")


def _credit_sums_to_one(frame: pd.DataFrame) -> bool:
    totals = frame.groupby("conversion_id", sort=False)["credit"].sum()
    return bool(totals.sub(1.0).abs().le(1e-12).all())
