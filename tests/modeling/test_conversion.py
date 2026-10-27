"""Tests for the leakage-safe conversion propensity model."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from marketing_measurement.modeling import conversion
from marketing_measurement.modeling.conversion import (
    HeldOutData,
    LeakageError,
    build_feature_matrix,
    evaluate_conversion_model,
    train_conversion_model,
)


@pytest.fixture(autouse=True)
def small_parameter_grids(monkeypatch: pytest.MonkeyPatch) -> None:
    """One configuration per family keeps unit tests fast; the grid logic is shared."""
    monkeypatch.setattr(
        conversion,
        "PARAMETER_GRIDS",
        {
            "logistic_regression": ({"classifier__C": 1.0},),
            "gradient_boosting": ({"classifier__learning_rate": 0.1},),
        },
    )


@pytest.fixture
def training_frame() -> pd.DataFrame:
    """Small, balanced-enough pre-outcome session sample."""
    rows: list[dict[str, object]] = []
    for index in range(300):
        converted = index % 7 == 0
        rows.append(
            {
                "session_start_date": (
                    f"{('2020-11', '2020-12', '2021-01')[index % 3]}-{(index % 28) + 1:02d}"
                ),
                "session_start_hour": index % 24,
                "session_start_day_of_week": index % 7,
                "device_category": "mobile" if index % 2 else "desktop",
                "country_group": "United States" if index % 3 else "Other",
                "new_returning_status": "new" if index % 4 else "returning",
                "session_source": "google" if converted else "direct",
                "session_medium": "organic" if converted else "(none)",
                "session_campaign": "brand" if converted else "(none)",
                "user_group_bucket": index,
                "converted": converted,
            }
        )
    return pd.DataFrame(rows)


def test_post_conversion_columns_are_rejected(training_frame: pd.DataFrame) -> None:
    with pytest.raises(LeakageError, match="purchase_revenue"):
        build_feature_matrix(training_frame, ["device_category", "purchase_revenue"])


@pytest.mark.parametrize(
    "unexpected_column",
    [
        "converted",
        "user_pseudo_id",
        "ga_session_id",
        "transaction_id",
        "refund_value",
        "engagement_score",
        "cart_value",
        "checkout_step",
        "purchase_revenue",
        "session_duration_seconds",
        "later_page_path",
        "arbitrary_unknown_field",
        "session_start_date",
        "user_group_bucket",
    ],
)
def test_only_exact_preoutcome_allowlist_is_accepted(
    training_frame: pd.DataFrame, unexpected_column: str
) -> None:
    training_frame[unexpected_column] = "unexpected"

    with pytest.raises(LeakageError, match=re.escape(unexpected_column)):
        build_feature_matrix(training_frame, ["device_category", unexpected_column])


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
    assert set(report.model_metrics) == {"logistic_regression", "gradient_boosting"}
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


def test_training_rejects_unapproved_input_columns(
    training_frame: pd.DataFrame,
) -> None:
    features = training_frame.drop(columns="converted").assign(refund_value=0.0)

    with pytest.raises(LeakageError, match="refund_value"):
        train_conversion_model(
            features, training_frame["converted"], training_frame["user_group_bucket"]
        )


def test_capacity_threshold_is_frozen_from_training_oof_only(
    training_frame: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    sizes_seen: list[int] = []
    original = conversion._capacity_threshold

    def record_training_oof_size(probability: object) -> float:
        sizes_seen.append(len(probability))  # type: ignore[arg-type]
        return original(probability)  # type: ignore[arg-type]

    monkeypatch.setattr(conversion, "_capacity_threshold", record_training_oof_size)
    features = training_frame.drop(columns="converted")
    bundle = train_conversion_model(
        features, training_frame["converted"], training_frame["user_group_bucket"]
    )
    first_report = evaluate_conversion_model(bundle, bundle.test)
    changed_test = HeldOutData(
        features=bundle.test.features.assign(session_source="changed-after-training"),
        target=1 - bundle.test.target,
        groups=bundle.test.groups,
    )
    second_report = evaluate_conversion_model(bundle, changed_test)

    assert sizes_seen == [bundle.split_metadata["training_rows"]]
    assert first_report.selected_threshold == bundle.selected_threshold
    assert second_report.selected_threshold == bundle.selected_threshold


def test_observed_session_sample_has_no_unique_identifier_columns() -> None:
    path = (
        Path(__file__).parents[2]
        / "data/observed/ga4_public_sample/conversion_model_sessions.json.gz"
    )
    sessions = pd.read_json(path)

    assert len(sessions) == 33_553
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


def test_manifest_distinguishes_session_model_data_from_aggregates() -> None:
    root = Path(__file__).parents[2]
    manifest = json.loads((root / "data/manifests/ga4_sample.json").read_text())
    metadata = json.loads(
        (root / "data/observed/ga4_public_sample/retrieval_metadata.json").read_text()
    )

    checksums = manifest["checksums"]
    assert "observed_identifier_free_session_model_data" in checksums
    assert "conversion_model_sessions.json.gz" not in checksums[
        "observed_aggregate_outputs"
    ]["files"]
    assert metadata["queries"]["conversion_model_sessions"]["result_category"] == (
        "identifier_free_session_model_data"
    )


def test_report_includes_returning_rule_baseline_and_intervals(
    training_frame: pd.DataFrame,
) -> None:
    features = training_frame.drop(columns="converted")
    bundle = train_conversion_model(
        features, training_frame["converted"], training_frame["user_group_bucket"]
    )
    report = evaluate_conversion_model(bundle, bundle.test)

    assert set(bundle.heuristic_rates) <= {"new", "returning"}
    assert set(report.heuristic_metrics) == {"roc_auc", "pr_auc", "brier_score"}
    for lower, upper in report.bootstrap_intervals.values():
        assert lower <= upper


def test_cluster_bootstrap_keeps_groups_whole_and_is_reproducible() -> None:
    import numpy as np

    rng = np.random.default_rng(0)
    target = np.tile([1, 0, 0, 0, 0], 40)
    probability = np.where(target == 1, 0.8, 0.2) + rng.uniform(-0.15, 0.15, 200)
    heuristic = np.full(200, 0.2)
    groups = np.repeat(np.arange(40), 5)

    first = conversion.grouped_bootstrap_intervals(
        target, probability, heuristic, 0.5, groups, replicates=200
    )
    second = conversion.grouped_bootstrap_intervals(
        target, probability, heuristic, 0.5, groups, replicates=200
    )

    assert first == second
    assert first["roc_auc"] == pytest.approx((1.0, 1.0))
    low, high = first["pr_auc_gain_over_heuristic"]
    assert 0 < low <= high


def test_cluster_bootstrap_rejects_mismatched_lengths() -> None:
    import numpy as np

    with pytest.raises(ValueError, match="equal lengths"):
        conversion.grouped_bootstrap_intervals(
            np.array([0, 1]), np.array([0.1]), np.array([0.1, 0.2]), 0.5, np.array([1, 2])
        )


def test_logistic_fit_is_independent_of_row_order() -> None:
    """A converged convex fit must not depend on floating-point summation order.

    The earlier early-stopped L-BFGS fit moved the held-out queue between 317 and
    329 sessions under row permutations alone, and differed between macOS and Linux.
    """
    import numpy as np

    sessions = pd.read_json(
        Path(__file__).parents[2]
        / "data/observed/ga4_public_sample/conversion_model_sessions.json.gz"
    )
    features = sessions.loc[:, list(conversion.APPROVED_MODEL_FEATURES)]
    target = conversion._binary_target(sessions["converted"])
    order = np.random.default_rng(0).permutation(len(sessions))

    def fitted_scores(rows: np.ndarray) -> np.ndarray:
        pipeline = conversion._candidate_pipelines(features)["logistic_regression"]
        pipeline.fit(features.iloc[rows], target.iloc[rows])
        return np.asarray(pipeline.predict_proba(features)[:, 1])

    original = fitted_scores(np.arange(len(sessions)))
    permuted = fitted_scores(order)

    assert np.abs(original - permuted).max() < 1e-9
