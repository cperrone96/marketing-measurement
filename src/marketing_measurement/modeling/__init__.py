"""Leakage-safe predictive modeling helpers for the public GA4 sample."""

from .conversion import (
    EvaluationReport,
    LeakageError,
    ModelBundle,
    build_feature_matrix,
    evaluate_conversion_model,
    train_conversion_model,
)

__all__ = [
    "EvaluationReport",
    "LeakageError",
    "ModelBundle",
    "build_feature_matrix",
    "evaluate_conversion_model",
    "train_conversion_model",
]
