"""Tests for descriptive multi-touch attribution credit rules."""

from __future__ import annotations

import pandas as pd
import pytest

from marketing_measurement.analysis.attribution import (
    attribution_credits,
    default_channel_group,
    expand_paths,
    is_internal_referral,
    weighted_credits,
)


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


def test_time_decay_halves_weight_for_each_earlier_touch() -> None:
    paths = pd.DataFrame(
        {
            "conversion_id": ["c"] * 3,
            "channel": ["a", "b", "c"],
            "touch_number": [1, 2, 3],
        }
    )
    credits = attribution_credits(paths, "time_decay")["credit"].tolist()

    assert credits == pytest.approx([1 / 7, 2 / 7, 4 / 7])


@pytest.mark.parametrize(
    ("touch", "group"),
    [
        ("google / organic", "Organic Search"),
        ("<Other> / organic", "Organic Search"),
        ("google / cpc", "Paid Search"),
        ("(direct) / (none)", "Direct"),
        ("Newsletter_December_2020 / email", "Email"),
        ("Partners / affiliate", "Affiliates"),
        ("l.facebook.com / referral", "Organic Social"),
        ("youtube.com / referral", "Organic Video"),
        ("mail.google.com / referral", "Referral"),
        ("shop.googlemerchandisestore.com / referral", "Internal self-referral"),
        ("googlemerchandisestore.com / referral", "Internal self-referral"),
        ("(data deleted) / (data deleted)", "Unassigned"),
        ("(unattributed) / (unattributed)", "Unassigned"),
        ("<Other> / <Other>", "Unassigned"),
    ],
)
def test_default_channel_group_rules(touch: str, group: str) -> None:
    assert default_channel_group(touch) == group


def test_lookalike_domain_is_not_treated_as_internal() -> None:
    assert not is_internal_referral("notgooglemerchandisestore.com / referral")


def test_excluding_self_referrals_falls_back_to_direct_and_keeps_weights() -> None:
    paths = pd.DataFrame(
        {
            "channel_path": [
                "google / organic > shop.googlemerchandisestore.com / referral",
                "shop.googlemerchandisestore.com / referral",
            ],
            "converted_sessions": [3, 2],
        }
    )
    touches = expand_paths(paths, exclude_internal_referrals=True)

    assert touches["channel"].tolist() == ["google / organic", "(direct) / (none)"]
    last = weighted_credits(touches, "last_touch")
    assert last.to_dict() == {"google / organic": 3.0, "(direct) / (none)": 2.0}
    assert weighted_credits(touches, "linear", by_channel_group=True).sum() == 5.0
