"""Tests for the leakage-safe conversion propensity model."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marketing_measurement.modeling.conversion import (
    LeakageError,
    build_feature_matrix,
    evaluate_conversion_model,
    train_conversion_model,
)


@pytest.fixture
def training_frame() -> pd.DataFrame:
    """Small, balanced-enough pre-outcome session sample."""
    rows: list[dict[str, object]] = []
    for index in range(100):
        converted = index % 5 == 0
        rows.append(
            {
                "session_start_date": f"2020-11-{(index % 28) + 1:02d}",
                "session_start_hour": index % 24,
                "session_start_day_of_week": index % 7,
                "device_category": "mobile" if index % 2 else "desktop",
                "country_group": "United States" if index % 3 else "Other",
                "new_returning_status": "new" if index % 4 else "returning",
                "session_source": "google" if converted else "direct",
                "session_medium": "organic" if converted else "(none)",
                "user_group_bucket": index,
                "converted": converted,
            }
        )
    return pd.DataFrame(rows)


def test_post_conversion_columns_are_rejected(training_frame: pd.DataFrame) -> None:
    with pytest.raises(LeakageError, match="purchase_revenue"):
        build_feature_matrix(training_frame, ["device_category", "purchase_revenue"])


def test_report_contains_baseline_and_calibration(training_frame: pd.DataFrame) -> None:
    features = training_frame.drop(columns="converted")
    bundle = train_conversion_model(
        features,
        training_frame["converted"],
        training_frame["user_group_bucket"],
    )

    report = evaluate_conversion_model(bundle, bundle.test)

    assert report.baseline_pr_auc is not None
    assert report.brier_score is not None
    assert report.threshold_table.shape[0] >= 3
    assert set(report.model_metrics) == {"logistic_regression", "random_forest"}
    assert report.confusion_matrix.shape == (2, 2)
    assert not report.calibration_bins.empty


def test_json_boolean_strings_are_not_all_treated_as_conversions(
    training_frame: pd.DataFrame,
) -> None:
    features = training_frame.drop(columns="converted")
    string_target = training_frame["converted"].map({True: "true", False: "false"})

    bundle = train_conversion_model(
        features, string_target, training_frame["user_group_bucket"]
    )

    assert bundle.training_prevalence < 0.5


def test_observed_session_sample_has_no_unique_identifier_columns() -> None:
    path = (
        Path(__file__).parents[2]
        / "data/observed/ga4_public_sample/conversion_model_sessions.json.gz"
    )
    sessions = pd.read_json(path)

    assert len(sessions) == 36_211
    assert sessions.columns.tolist() == [
        "converted",
        "country_group",
        "device_category",
        "new_returning_status",
        "session_campaign",
        "session_medium",
        "session_source",
        "session_start_date",
        "session_start_day_of_week",
        "session_start_hour",
        "user_group_bucket",
    ]
    assert not any(
        token in column.lower()
        for column in sessions.columns
        for token in ("pseudo", "transaction", "session_id", "event_id")
    )
    assert sessions["user_group_bucket"].nunique() < len(sessions)
