"""Tests for descriptive multi-touch attribution credit rules."""

from __future__ import annotations

import pandas as pd
import pytest

from marketing_measurement.analysis.attribution import attribution_credits


@pytest.fixture
def sample_paths() -> pd.DataFrame:
    """Compact, non-identifying converted paths in chronological order."""
    return pd.DataFrame(
        {
            "conversion_id": ["conversion-a", "conversion-a", "conversion-b"],
            "channel": ["organic", "email", "paid_search"],
            "touch_number": [1, 2, 1],
        }
    )


@pytest.mark.parametrize("model", ["first_touch", "last_touch", "linear", "time_decay"])
def test_conversion_credit_sums_to_one(sample_paths: pd.DataFrame, model: str) -> None:
    credits = attribution_credits(sample_paths, model)

    totals = credits.groupby("conversion_id")["credit"].sum()
    assert totals.tolist() == pytest.approx([1.0] * len(totals))


def test_first_and_last_touch_credit_expected_channels(sample_paths: pd.DataFrame) -> None:
    first = attribution_credits(sample_paths, "first_touch")
    last = attribution_credits(sample_paths, "last_touch")

    assert first.loc[first["conversion_id"] == "conversion-a", "credit"].tolist() == [1.0, 0.0]
    assert last.loc[last["conversion_id"] == "conversion-a", "credit"].tolist() == [0.0, 1.0]


def test_attribution_is_explicitly_descriptive(sample_paths: pd.DataFrame) -> None:
    credits = attribution_credits(sample_paths, "linear")

    assert credits["interpretation"].unique().tolist() == [
        "descriptive attribution; not causal"
    ]


def test_unknown_model_is_rejected(sample_paths: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="Unsupported attribution model"):
        attribution_credits(sample_paths, "incrementality")
