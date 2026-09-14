"""Grouped, leakage-safe conversion propensity modeling for session observations.

This module is intentionally decision support for an educational portfolio.  It does
not estimate causal lift or prescribe real-campaign targeting.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve  # type: ignore[import-untyped]
from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.ensemble import RandomForestClassifier  # type: ignore[import-untyped]
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (  # type: ignore[import-untyped]
    GroupKFold,
    GroupShuffleSplit,
    cross_validate,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import OneHotEncoder  # type: ignore[import-untyped]

RANDOM_STATE = 20260911
HOLDOUT_FRACTION = 0.20
OUTREACH_CAPACITY_PER_1000 = 50
DATE_COLUMN = "session_start_date"
GROUP_COLUMN = "user_group_bucket"
LEAKAGE_TERMS = (
    "purchase",
    "revenue",
    "transaction",
    "cart",
    "checkout",
    "engagement",
    "session_duration",
    "page_view",
    "conversion",
    "outcome",
)


class LeakageError(ValueError):
    """Raised when a feature could reflect behavior after conversion."""


@dataclass(frozen=True)
class HeldOutData:
    """Feature, target, and non-unique group columns reserved for one holdout."""

    features: pd.DataFrame
    target: pd.Series
    groups: pd.Series


@dataclass(frozen=True)
class ModelBundle:
    """Fitted pipelines and the holdout that was never used to fit them."""

    models: Mapping[str, Any]
    selected_model_name: str
    feature_columns: tuple[str, ...]
    training_prevalence: float
    cv_scores: Mapping[str, Mapping[str, float]]
    test: HeldOutData
    split_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class EvaluationReport:
    """Held-out discriminative, calibration, threshold, and subgroup evidence."""

    baseline_pr_auc: float
    baseline_roc_auc: float
    baseline_brier_score: float
    model_metrics: Mapping[str, Mapping[str, float]]
    brier_score: float
    calibration_bins: pd.DataFrame
    threshold_table: pd.DataFrame
    selected_threshold: float
    selected_threshold_label: str
    confusion_matrix: pd.DataFrame
    subgroup_diagnostics: pd.DataFrame


def build_feature_matrix(
    frame: pd.DataFrame, feature_columns: Sequence[str]
) -> pd.DataFrame:
    """Return only approved pre-outcome model inputs.

    ``session_start_date`` and ``user_group_bucket`` are retained by callers only for
    splitting and reporting; neither can enter a model pipeline.
    """

    forbidden = [
        column
        for column in feature_columns
        if any(term in column.lower() for term in LEAKAGE_TERMS)
    ]
    if forbidden:
        raise LeakageError(
            "Post-conversion or behavior-derived feature(s) are not allowed: "
            + ", ".join(forbidden)
        )
    missing = sorted(set(feature_columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Feature column(s) are missing: {', '.join(missing)}")
    model_columns = [
        column
        for column in feature_columns
        if column not in {DATE_COLUMN, GROUP_COLUMN}
    ]
    if not model_columns:
        raise ValueError("At least one approved pre-outcome model feature is required")
    return frame.loc[:, model_columns].copy()


def train_conversion_model(
    features: pd.DataFrame, target: pd.Series, groups: pd.Series
) -> ModelBundle:
    """Fit baselines on a group-disjoint holdout and group-confined CV folds."""

    _validate_training_inputs(features, target, groups)
    feature_matrix = build_feature_matrix(features, list(features.columns))
    target_binary = _binary_target(target).reset_index(drop=True)
    groups_clean = groups.reset_index(drop=True)
    feature_matrix = feature_matrix.reset_index(drop=True)
    original_features = features.reset_index(drop=True)
    train_index, test_index, split_seed = _group_holdout_indices(
        target_binary, groups_clean
    )
    x_train = feature_matrix.iloc[train_index]
    y_train = target_binary.iloc[train_index]
    group_train = groups_clean.iloc[train_index]
    x_test = feature_matrix.iloc[test_index]
    y_test = target_binary.iloc[test_index]
    group_test = groups_clean.iloc[test_index]
    pipelines = _candidate_pipelines(x_train)
    cv_splits = min(5, int(group_train.nunique()))
    if cv_splits < 2:
        raise ValueError("At least two non-unique user-group buckets are required")
    splitter = GroupKFold(n_splits=cv_splits)
    cv_scores: dict[str, Mapping[str, float]] = {}
    fitted: dict[str, Any] = {}
    scoring = {
        "roc_auc": "roc_auc",
        "pr_auc": "average_precision",
        "brier": "neg_brier_score",
    }
    for name, pipeline in pipelines.items():
        scored = cross_validate(
            pipeline,
            x_train,
            y_train,
            groups=group_train,
            cv=splitter,
            scoring=scoring,
            n_jobs=1,
            error_score="raise",
        )
        cv_scores[name] = {
            "roc_auc": float(np.mean(scored["test_roc_auc"])),
            "pr_auc": float(np.mean(scored["test_pr_auc"])),
            "brier_score": float(-np.mean(scored["test_brier"])),
        }
        fitted[name] = pipeline.fit(x_train, y_train)
    selected = max(cv_scores, key=lambda name: cv_scores[name]["pr_auc"])
    split_metadata = {
        "method": "group_shuffle_split",
        "group_column": GROUP_COLUMN,
        "holdout_fraction_target": HOLDOUT_FRACTION,
        "holdout_rows": len(test_index),
        "training_rows": len(train_index),
        "random_state": split_seed,
        "cv": f"GroupKFold(n_splits={cv_splits}) on training data only",
        "group_overlap_count": len(set(group_train).intersection(set(group_test))),
        "date_range": _date_range(original_features),
    }
    return ModelBundle(
        models=fitted,
        selected_model_name=selected,
        feature_columns=tuple(feature_matrix.columns),
        training_prevalence=float(y_train.mean()),
        cv_scores=cv_scores,
        test=HeldOutData(
            features=x_test.assign(
                **_reporting_columns(original_features.iloc[test_index], x_test.index)
            ),
            target=y_test,
            groups=group_test,
        ),
        split_metadata=split_metadata,
    )


def evaluate_conversion_model(
    bundle: ModelBundle, test: HeldOutData
) -> EvaluationReport:
    """Evaluate fitted models once on a previously untouched grouped holdout."""

    x_test = test.features.loc[:, list(bundle.feature_columns)]
    y_test = _binary_target(test.target)
    model_metrics: dict[str, Mapping[str, float]] = {}
    predictions: dict[str, np.ndarray] = {}
    for name, model in bundle.models.items():
        probability = np.asarray(model.predict_proba(x_test)[:, 1])
        predictions[name] = probability
        model_metrics[name] = _probability_metrics(y_test, probability)
    selected_probability = predictions[bundle.selected_model_name]
    baseline_probability = np.full(len(y_test), bundle.training_prevalence)
    baseline = _probability_metrics(y_test, baseline_probability)
    selected_threshold = _capacity_threshold(selected_probability)
    threshold_table = _threshold_table(y_test, selected_probability, selected_threshold)
    selected_predictions = (selected_probability >= selected_threshold).astype(int)
    matrix = confusion_matrix(y_test, selected_predictions, labels=[0, 1])
    calibration = _calibration_bins(y_test, selected_probability)
    return EvaluationReport(
        baseline_pr_auc=baseline["pr_auc"],
        baseline_roc_auc=baseline["roc_auc"],
        baseline_brier_score=baseline["brier_score"],
        model_metrics=model_metrics,
        brier_score=model_metrics[bundle.selected_model_name]["brier_score"],
        calibration_bins=calibration,
        threshold_table=threshold_table,
        selected_threshold=selected_threshold,
        selected_threshold_label=(
            f"capacity_{OUTREACH_CAPACITY_PER_1000}_per_1000_sessions"
        ),
        confusion_matrix=pd.DataFrame(
            matrix,
            index=pd.Index(["actual_negative", "actual_positive"], name="actual"),
            columns=pd.Index(
                ["predicted_negative", "predicted_positive"], name="prediction"
            ),
        ),
        subgroup_diagnostics=_subgroup_diagnostics(
            test.features, y_test, selected_predictions
        ),
    )


def _validate_training_inputs(
    features: pd.DataFrame, target: pd.Series, groups: pd.Series
) -> None:
    if len(features) != len(target) or len(features) != len(groups):
        raise ValueError("features, target, and groups must have equal row counts")
    if len(features) < 20:
        raise ValueError("At least 20 measured sessions are required")
    if _binary_target(target).nunique() != 2:
        raise ValueError("The conversion target must contain both outcome classes")
    if groups.isna().any():
        raise ValueError("Non-unique user-group buckets cannot be missing")


def _binary_target(target: pd.Series) -> pd.Series:
    """Normalize JSON-exported booleans without treating the string ``false`` as true."""

    if pd.api.types.is_bool_dtype(target):
        return target.astype(int)
    normalized = target.astype(str).str.strip().str.lower()
    accepted = {"true": 1, "false": 0, "1": 1, "0": 0}
    if not normalized.isin(accepted).all():
        raise ValueError("The conversion target must contain boolean values")
    return normalized.map(accepted).astype(int)


def _candidate_pipelines(features: pd.DataFrame) -> Mapping[str, Any]:
    numeric = features.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical = [column for column in features.columns if column not in numeric]
    transformers: list[tuple[str, Any, list[str]]] = []
    if numeric:
        transformers.append(
            (
                "numeric",
                Pipeline([("impute", SimpleImputer(strategy="median"))]),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "one_hot",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                categorical,
            )
        )
    preprocessor = ColumnTransformer(transformers=transformers, remainder="drop")
    return {
        "logistic_regression": Pipeline(
            [
                ("preprocess", preprocessor),
                (
                    "classifier",
                    LogisticRegression(max_iter=1_000, random_state=RANDOM_STATE),
                ),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("preprocess", preprocessor),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=200,
                        min_samples_leaf=5,
                        class_weight="balanced_subsample",
                        n_jobs=1,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def _group_holdout_indices(
    target: pd.Series, groups: pd.Series
) -> tuple[np.ndarray, np.ndarray, int]:
    """Find a deterministic group-disjoint split containing both outcome classes."""

    candidates: list[tuple[float, np.ndarray, np.ndarray, int]] = []
    for offset in range(100):
        seed = RANDOM_STATE + offset
        splitter = GroupShuffleSplit(
            n_splits=1, test_size=HOLDOUT_FRACTION, random_state=seed
        )
        train_index, test_index = next(splitter.split(target, target, groups))
        if (
            target.iloc[train_index].nunique() == 2
            and target.iloc[test_index].nunique() == 2
        ):
            score = abs(len(test_index) / len(target) - HOLDOUT_FRACTION)
            candidates.append((score, train_index, test_index, seed))
    if not candidates:
        raise ValueError(
            "Could not make a group-disjoint split with both outcome classes"
        )
    _, train_index, test_index, seed = min(candidates, key=lambda value: value[0])
    return train_index, test_index, seed


def _date_range(features: pd.DataFrame) -> Mapping[str, str | None]:
    if DATE_COLUMN not in features:
        return {"start": None, "end": None}
    dates = pd.to_datetime(features[DATE_COLUMN], errors="coerce")
    return {
        "start": dates.min().date().isoformat() if dates.notna().any() else None,
        "end": dates.max().date().isoformat() if dates.notna().any() else None,
    }


def _reporting_columns(
    original: pd.DataFrame, index: pd.Index
) -> Mapping[str, pd.Series]:
    columns = [
        column
        for column in ("device_category", "country_group", "new_returning_status")
        if column in original
    ]
    return {
        column: original[column].reset_index(drop=True).set_axis(index)
        for column in columns
    }


def _probability_metrics(
    target: pd.Series, probability: np.ndarray
) -> Mapping[str, float]:
    return {
        "roc_auc": float(roc_auc_score(target, probability)),
        "pr_auc": float(average_precision_score(target, probability)),
        "brier_score": float(brier_score_loss(target, probability)),
    }


def _capacity_threshold(probability: np.ndarray) -> float:
    capacity = max(
        1, int(np.ceil(len(probability) * OUTREACH_CAPACITY_PER_1000 / 1000))
    )
    return float(np.sort(probability)[-capacity])


def _threshold_table(
    target: pd.Series, probability: np.ndarray, capacity_threshold: float
) -> pd.DataFrame:
    thresholds: list[tuple[str, float]] = [
        ("0.05", 0.05),
        ("0.10", 0.10),
        ("0.20", 0.20),
        ("0.30", 0.30),
        ("0.50", 0.50),
        (f"capacity_{OUTREACH_CAPACITY_PER_1000}_per_1000", capacity_threshold),
    ]
    rows: list[Mapping[str, float | int | str]] = []
    for label, threshold in thresholds:
        predicted = (probability >= threshold).astype(int)
        rows.append(
            {
                "scenario": label,
                "threshold": threshold,
                "flagged_sessions": int(predicted.sum()),
                "flagged_per_1000": float(predicted.mean() * 1000),
                "precision": float(precision_score(target, predicted, zero_division=0)),
                "recall": float(recall_score(target, predicted, zero_division=0)),
            }
        )
    return pd.DataFrame(rows)


def _calibration_bins(target: pd.Series, probability: np.ndarray) -> pd.DataFrame:
    observed, predicted = calibration_curve(
        target, probability, n_bins=5, strategy="quantile"
    )
    return pd.DataFrame(
        {"mean_predicted_probability": predicted, "observed_conversion_rate": observed}
    )


def _subgroup_diagnostics(
    features: pd.DataFrame, target: pd.Series, prediction: np.ndarray
) -> pd.DataFrame:
    rows: list[Mapping[str, float | int | str]] = []
    for column in ("device_category", "country_group", "new_returning_status"):
        if column not in features:
            continue
        values = features[column].fillna("(missing)").astype(str)
        for group, indexes in values.groupby(values, sort=True).groups.items():
            y_group = target.loc[indexes]
            predicted_group = prediction[pd.Index(target.index).get_indexer(indexes)]
            rows.append(
                {
                    "dimension": column,
                    "group": str(group),
                    "sessions": len(y_group),
                    "conversions": int(y_group.sum()),
                    "prevalence": float(y_group.mean()),
                    "flagged_sessions": int(predicted_group.sum()),
                    "precision": float(
                        precision_score(y_group, predicted_group, zero_division=0)
                    ),
                    "recall": float(
                        recall_score(y_group, predicted_group, zero_division=0)
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(["dimension", "group"]).reset_index(drop=True)
