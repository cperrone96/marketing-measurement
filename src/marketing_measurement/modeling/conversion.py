"""Leakage-safe conversion propensity modeling for session observations.

Validation mirrors deployment: the model is trained on earlier sessions and scored
once on a later month it never saw. Inside the training period, an L2 logistic
regression and a histogram gradient-boosting model are tuned and compared with
user-bucket ``GroupKFold`` cross-validation. The held-out month is scored against
two baselines (training prevalence and a one-feature returning-visitor rule), with
cluster-bootstrap intervals, calibration diagnostics and permutation importance.
Predictions describe association, not causal lift.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve  # type: ignore[import-untyped]
from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.ensemble import (  # type: ignore[import-untyped]
    HistGradientBoostingClassifier,
)
from sklearn.impute import SimpleImputer  # type: ignore[import-untyped]
from sklearn.inspection import permutation_importance  # type: ignore[import-untyped]
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
    cross_val_predict,
    cross_validate,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import (  # type: ignore[import-untyped]
    OneHotEncoder,
    OrdinalEncoder,
    StandardScaler,
)

RANDOM_STATE = 20260911
#: Sessions on or after this date form the untouched forward-in-time holdout.
TEMPORAL_CUTOFF = "2021-01-01"
#: Hyperparameter grids searched with grouped CV inside the training period only.
PARAMETER_GRIDS: Mapping[str, tuple[Mapping[str, Any], ...]] = {
    "logistic_regression": tuple(
        {"classifier__C": c} for c in (0.01, 0.1, 1.0, 10.0)
    ),
    "gradient_boosting": tuple(
        {"classifier__learning_rate": rate, "classifier__max_leaf_nodes": leaves}
        for rate in (0.03, 0.1)
        for leaves in (7, 15)
    ),
}
OUTREACH_CAPACITY_PER_1000 = 50
BOOTSTRAP_REPLICATES = 2_000
HEURISTIC_FEATURE = "new_returning_status"
DATE_COLUMN = "session_start_date"
GROUP_COLUMN = "user_group_bucket"
APPROVED_MODEL_FEATURES = (
    "session_start_hour",
    "session_start_day_of_week",
    "device_category",
    "country_group",
    "new_returning_status",
    "session_source",
    "session_medium",
    "session_campaign",
)
APPROVED_INPUT_COLUMNS = frozenset(
    (*APPROVED_MODEL_FEATURES, DATE_COLUMN, GROUP_COLUMN)
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
    selected_threshold: float
    test: HeldOutData
    split_metadata: Mapping[str, Any]
    heuristic_rates: Mapping[str, float]
    best_parameters: Mapping[str, Mapping[str, Any]]


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
    heuristic_metrics: Mapping[str, float]
    bootstrap_intervals: Mapping[str, tuple[float, float]]
    threshold_margin: float
    calibration_summary: Mapping[str, float]
    permutation_importance: pd.DataFrame


def build_feature_matrix(
    frame: pd.DataFrame, feature_columns: Sequence[str]
) -> pd.DataFrame:
    """Return only approved pre-outcome model inputs.

    This is an exact allowlist, not a substring blacklist. ``session_start_date`` and
    ``user_group_bucket`` are split/provenance fields and cannot enter a model.
    """

    unexpected = sorted(set(feature_columns).difference(APPROVED_MODEL_FEATURES))
    if unexpected:
        raise LeakageError(
            "Feature(s) are not on the approved pre-outcome allowlist: "
            + ", ".join(unexpected)
        )
    missing = sorted(set(feature_columns).difference(frame.columns))
    if missing:
        raise ValueError(f"Feature column(s) are missing: {', '.join(missing)}")
    return frame.loc[:, list(feature_columns)].copy()


def train_conversion_model(
    features: pd.DataFrame,
    target: pd.Series,
    groups: pd.Series,
    temporal_cutoff: str = TEMPORAL_CUTOFF,
) -> ModelBundle:
    """Tune and select on earlier sessions; hold out every later session untouched."""

    _validate_training_inputs(features, target, groups)
    feature_matrix = build_feature_matrix(features, APPROVED_MODEL_FEATURES)
    target_binary = _binary_target(target).reset_index(drop=True)
    groups_clean = groups.reset_index(drop=True)
    feature_matrix = feature_matrix.reset_index(drop=True)
    original_features = features.reset_index(drop=True)
    train_index, test_index = _temporal_holdout_indices(
        original_features, target_binary, temporal_cutoff
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
    cv_folds = list(
        GroupKFold(n_splits=cv_splits).split(x_train, y_train, group_train)
    )
    scoring = {
        "roc_auc": "roc_auc",
        "pr_auc": "average_precision",
        "brier": "neg_brier_score",
    }
    cv_scores: dict[str, Mapping[str, float]] = {}
    best_parameters: dict[str, Mapping[str, Any]] = {}
    fitted: dict[str, Any] = {}
    for name, pipeline in pipelines.items():
        best: tuple[float, Mapping[str, Any], Mapping[str, float]] | None = None
        for parameters in PARAMETER_GRIDS[name]:
            scored = cross_validate(
                pipeline.set_params(**parameters),
                x_train,
                y_train,
                cv=cv_folds,
                scoring=scoring,
                n_jobs=1,
                error_score="raise",
            )
            scores = {
                "roc_auc": float(np.mean(scored["test_roc_auc"])),
                "pr_auc": float(np.mean(scored["test_pr_auc"])),
                "brier_score": float(-np.mean(scored["test_brier"])),
            }
            if best is None or scores["pr_auc"] > best[0]:
                best = (scores["pr_auc"], parameters, scores)
        assert best is not None
        _, best_parameters[name], cv_scores[name] = best
        fitted[name] = pipeline.set_params(**best_parameters[name]).fit(
            x_train, y_train
        )
    selected = max(cv_scores, key=lambda name: cv_scores[name]["pr_auc"])
    selected_oof_probability = np.asarray(
        cross_val_predict(
            pipelines[selected],
            x_train,
            y_train,
            cv=cv_folds,
            method="predict_proba",
            n_jobs=1,
        )[:, 1]
    )
    selected_threshold = _capacity_threshold(selected_oof_probability)
    training_prevalence = float(y_train.mean())
    heuristic_rates = _fit_rate_heuristic(x_train[HEURISTIC_FEATURE], y_train)
    split_metadata = {
        "method": "temporal_holdout",
        "temporal_cutoff": temporal_cutoff,
        "training_rows": len(train_index),
        "holdout_rows": len(test_index),
        "training_date_range": _date_range(original_features.iloc[train_index]),
        "holdout_date_range": _date_range(original_features.iloc[test_index]),
        "cv": f"GroupKFold(n_splits={cv_splits}) on {GROUP_COLUMN}, training only",
        "tuning": "grid search on mean grouped-CV PR-AUC, training only",
        "threshold_source": "grouped_out_of_fold_training_predictions",
        "threshold_oof_rows": len(selected_oof_probability),
    }
    return ModelBundle(
        models=fitted,
        selected_model_name=selected,
        feature_columns=tuple(feature_matrix.columns),
        training_prevalence=training_prevalence,
        cv_scores=cv_scores,
        selected_threshold=selected_threshold,
        test=HeldOutData(
            features=x_test.assign(
                **_reporting_columns(original_features.iloc[test_index], x_test.index)
            ),
            target=y_test,
            groups=group_test,
        ),
        split_metadata=split_metadata,
        heuristic_rates=heuristic_rates,
        best_parameters=best_parameters,
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
    selected_threshold = bundle.selected_threshold
    threshold_table = _threshold_table(y_test, selected_probability, selected_threshold)
    selected_predictions = (selected_probability >= selected_threshold).astype(int)
    matrix = confusion_matrix(y_test, selected_predictions, labels=[0, 1])
    calibration = _calibration_bins(y_test, selected_probability)
    heuristic_probability = _score_rate_heuristic(
        test.features[HEURISTIC_FEATURE],
        bundle.heuristic_rates,
        bundle.training_prevalence,
    )
    heuristic = _probability_metrics(y_test, heuristic_probability)
    intervals = grouped_bootstrap_intervals(
        y_test.to_numpy(),
        selected_probability,
        heuristic_probability,
        selected_threshold,
        test.groups.to_numpy(),
    )
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
        heuristic_metrics=heuristic,
        bootstrap_intervals=intervals,
        threshold_margin=float(np.min(np.abs(selected_probability - selected_threshold))),
        calibration_summary=_calibration_summary(y_test, selected_probability),
        permutation_importance=_permutation_importance(
            bundle.models[bundle.selected_model_name], x_test, y_test
        ),
    )


def grouped_bootstrap_intervals(
    target: np.ndarray,
    probability: np.ndarray,
    heuristic_probability: np.ndarray,
    threshold: float,
    groups: np.ndarray,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = RANDOM_STATE,
) -> Mapping[str, tuple[float, float]]:
    """Percentile 95% intervals from a cluster bootstrap over split groups.

    Whole groups are resampled with replacement, so sessions that share a user
    bucket stay together and the interval reflects between-user variation rather
    than treating sessions as independent. Replicates that draw a single outcome
    class are skipped (and counted) because ranking metrics are undefined there.
    """
    if not len(target) == len(probability) == len(heuristic_probability) == len(groups):
        raise ValueError("bootstrap inputs must have equal lengths")
    rng = np.random.default_rng(seed)
    unique_groups, group_codes = np.unique(groups, return_inverse=True)
    members = [np.flatnonzero(group_codes == code) for code in range(len(unique_groups))]
    flagged = probability >= threshold
    samples: dict[str, list[float]] = {
        "pr_auc": [],
        "roc_auc": [],
        "pr_auc_gain_over_heuristic": [],
        "capacity_precision": [],
        "capacity_recall": [],
        "capacity_lift": [],
    }
    for _ in range(replicates):
        drawn = rng.integers(0, len(members), size=len(members))
        index = np.concatenate([members[code] for code in drawn])
        y = target[index]
        positives = int(y.sum())
        if positives == 0 or positives == len(y):
            continue
        pr_auc = float(average_precision_score(y, probability[index]))
        samples["pr_auc"].append(pr_auc)
        samples["roc_auc"].append(float(roc_auc_score(y, probability[index])))
        samples["pr_auc_gain_over_heuristic"].append(
            pr_auc - float(average_precision_score(y, heuristic_probability[index]))
        )
        hits = int((y & flagged[index]).sum())
        precision = hits / max(1, int(flagged[index].sum()))
        samples["capacity_precision"].append(precision)
        samples["capacity_recall"].append(hits / positives)
        samples["capacity_lift"].append(precision / (positives / len(y)))
    if len(samples["pr_auc"]) < 0.95 * replicates:
        raise ValueError("too many single-class bootstrap replicates for stable intervals")
    return {
        name: (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))
        for name, values in samples.items()
    }


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
    unexpected = sorted(set(features.columns).difference(APPROVED_INPUT_COLUMNS))
    if unexpected:
        raise LeakageError(
            "Input contains columns outside the approved model/split/provenance "
            "allowlist: " + ", ".join(unexpected)
        )
    missing = sorted(set(APPROVED_MODEL_FEATURES).difference(features.columns))
    if missing:
        raise ValueError(
            "Required approved feature(s) are missing: " + ", ".join(missing)
        )


def _binary_target(target: pd.Series) -> pd.Series:
    """Normalize JSON-exported booleans without treating the string ``false`` as true."""

    if pd.api.types.is_bool_dtype(target):
        return target.astype(int)
    normalized = target.astype(str).str.strip().str.lower()
    accepted = {"true": 1, "false": 0, "1": 1, "0": 0}
    if not normalized.isin(accepted).all():
        raise ValueError("The conversion target must contain boolean values")
    return normalized.map(accepted).astype(int)


def _preprocessor(features: pd.DataFrame, *, scale_numeric: bool) -> ColumnTransformer:
    """Impute and one-hot encode inside each pipeline so CV folds never see test rows."""
    numeric = features.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical = [column for column in features.columns if column not in numeric]
    transformers: list[tuple[str, Any, list[str]]] = []
    if numeric:
        numeric_steps: list[tuple[str, Any]] = [
            ("impute", SimpleImputer(strategy="median"))
        ]
        if scale_numeric:
            numeric_steps.append(("scale", StandardScaler()))
        transformers.append(("numeric", Pipeline(numeric_steps), numeric))
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
    return ColumnTransformer(transformers=transformers, remainder="drop")


def _candidate_pipelines(features: pd.DataFrame) -> Mapping[str, Any]:
    """Return the two model families compared by grouped cross-validation.

    The logistic regression is solved with Newton's method on standardized inputs
    to a 1e-10 tolerance. L2-penalized logistic loss is strictly convex, so the fit
    is its unique optimum rather than wherever an early-stopped quasi-Newton run
    halted; an early-stopped fit depends on the platform's floating-point path.
    Gradient boosting uses native categorical splits on ordinal-encoded inputs and
    a fixed number of boosting rounds (no random early-stopping split).
    """
    numeric = features.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical = [column for column in features.columns if column not in numeric]
    ordinal = ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="median"), numeric),
            (
                "categorical",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=np.nan,
                    encoded_missing_value=np.nan,
                ),
                categorical,
            ),
        ],
        remainder="drop",
    )
    return {
        "logistic_regression": Pipeline(
            [
                ("preprocess", _preprocessor(features, scale_numeric=True)),
                (
                    "classifier",
                    LogisticRegression(
                        solver="newton-cholesky", tol=1e-10, max_iter=1_000
                    ),
                ),
            ]
        ),
        "gradient_boosting": Pipeline(
            [
                ("preprocess", ordinal),
                (
                    "classifier",
                    HistGradientBoostingClassifier(
                        max_iter=200,
                        min_samples_leaf=200,
                        l2_regularization=1.0,
                        early_stopping=False,
                        categorical_features=[False] * len(numeric)
                        + [True] * len(categorical),
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def _temporal_holdout_indices(
    features: pd.DataFrame, target: pd.Series, cutoff: str
) -> tuple[np.ndarray, np.ndarray]:
    """Train on sessions before ``cutoff``; hold out every session on or after it."""

    if DATE_COLUMN not in features:
        raise ValueError(f"{DATE_COLUMN} is required for the temporal holdout")
    dates = pd.to_datetime(features[DATE_COLUMN], errors="raise")
    is_holdout = (dates >= pd.Timestamp(cutoff)).to_numpy()
    train_index = np.flatnonzero(~is_holdout)
    test_index = np.flatnonzero(is_holdout)
    for label, index in (("training", train_index), ("holdout", test_index)):
        if target.iloc[index].nunique() != 2:
            raise ValueError(f"The {label} period must contain both outcome classes")
    return train_index, test_index


def _fit_rate_heuristic(feature: pd.Series, target: pd.Series) -> Mapping[str, float]:
    """Training conversion rate per category: a transparent one-rule baseline."""
    rates = target.groupby(feature.fillna("(missing)").astype(str)).mean()
    return {str(key): float(value) for key, value in rates.items()}


def _score_rate_heuristic(
    feature: pd.Series, rates: Mapping[str, float], fallback: float
) -> np.ndarray:
    """Score each row with its category's training rate (unseen: prevalence)."""
    keys = feature.fillna("(missing)").astype(str)
    return np.asarray(keys.map(rates).fillna(fallback), dtype=float)


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


def _calibration_summary(target: pd.Series, probability: np.ndarray) -> Mapping[str, float]:
    """Expected vs observed conversions and the logistic calibration slope.

    The slope is fit on the holdout for diagnosis only; nothing is recalibrated.
    A slope below one means scores are too extreme, above one too timid.
    """
    clipped = np.clip(probability, 1e-12, 1 - 1e-12)
    logit = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    slope_model = LogisticRegression(
        C=np.inf, solver="newton-cholesky", tol=1e-10, max_iter=1_000
    ).fit(logit, target)
    return {
        "expected_conversions": float(probability.sum()),
        "observed_conversions": float(target.sum()),
        "observed_to_expected_ratio": float(target.sum() / probability.sum()),
        "calibration_slope": float(slope_model.coef_[0][0]),
    }


def _permutation_importance(
    model: Any, features: pd.DataFrame, target: pd.Series
) -> pd.DataFrame:
    """Drop in held-out PR-AUC when each raw feature is shuffled (10 repeats)."""
    result = permutation_importance(
        model,
        features,
        target,
        scoring="average_precision",
        n_repeats=10,
        random_state=RANDOM_STATE,
        n_jobs=1,
    )
    return (
        pd.DataFrame(
            {
                "feature": features.columns,
                "pr_auc_drop_mean": result.importances_mean,
                "pr_auc_drop_std": result.importances_std,
            }
        )
        .sort_values("pr_auc_drop_mean", ascending=False, kind="stable")
        .reset_index(drop=True)
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
