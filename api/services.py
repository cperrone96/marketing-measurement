"""Service layer separating HTTP routes from reviewed artifact interpretation."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from api.repository import ArtifactRepository
from marketing_measurement.analysis.budget import (
    BudgetInputs,
    optimize_budget,
    scenario_sensitivity,
)
from marketing_measurement.simulation.integration import (
    SYNTHETIC_SEED,
    integration_health,
    simulate_integration_records,
)

MIN_DATE = date(2020, 11, 1)
MAX_DATE = date(2021, 1, 31)
SUPPORTED_BUDGET_CHANNELS = frozenset({"channel_aurora", "channel_birch"})

_PUBLIC_LIMITATIONS = [
    "The public sample is old, obfuscated, ecommerce-specific, and educational only.",
    "Observed results are descriptive and must not be generalized to client visitors.",
]
_SYNTHETIC_LIMITATIONS = [
    "This is a deterministic synthetic demonstration, not observed campaign evidence.",
    "Synthetic results do not estimate causal impact or forecast customer outcomes.",
]
class APIValidationError(ValueError):
    """Expected input error safely mapped to the public API error contract."""

    def __init__(self, code: str, message: str, details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def paginate[T](items: Sequence[T], page: int, page_size: int) -> tuple[list[T], int]:
    start = (page - 1) * page_size
    return list(items[start : start + page_size]), len(items)


class MarketingMeasurementService:
    """Creates public DTO dictionaries without letting routes calculate analytics."""

    def __init__(self, repository: ArtifactRepository | None = None) -> None:
        self._repository = repository or ArtifactRepository()

    def public_evidence(self, artifact: str, sha256: str) -> dict[str, Any]:
        source = self._repository.findings["source"]
        return {
            "evidence_type": "public_observed",
            "source_date_or_window": (
                f"{source['coverage_start']} through {source['coverage_end']}"
            ),
            "provenance": {"artifact": artifact, "sha256": sha256},
            "limitations": _PUBLIC_LIMITATIONS,
        }

    def synthetic_evidence(self, artifact: str) -> dict[str, Any]:
        digest = hashlib.sha256(artifact.encode()).hexdigest()
        return {
            "evidence_type": "synthetic",
            "source_date_or_window": f"deterministic scenario seed {SYNTHETIC_SEED}",
            "provenance": {"artifact": artifact, "sha256": digest},
            "limitations": _SYNTHETIC_LIMITATIONS,
        }

    def sources(self) -> tuple[str, list[dict[str, Any]]]:
        manifest = self._repository.manifest
        observed_hash = manifest["checksums"]["source_public_data_retrieval_metadata"]["value"]
        return (
            (
                "Each item is labeled by evidence type. Public-observed and "
                "synthetic evidence are intentionally not combined in a single result."
            ),
            [
                {
                    "name": "Google Analytics 4 public sample",
                    "description": "Reviewed compact aggregates and identifier-free model evidence.",
                    "evidence": self.public_evidence(
                        "public retrieval metadata", observed_hash
                    ),
                },
                {
                    "name": "Deterministic integration demonstrations",
                    "description": "Synthetic records used only for integration and scenario examples.",
                    "evidence": self.synthetic_evidence(
                        "synthetic integration fixture v1"
                    ),
                },
            ],
        )

    def kpis(self) -> list[dict[str, Any]]:
        findings = self._repository.findings
        return [
            {"name": "funnel", "values": findings["funnel"]},
            {"name": "day_7_retention", "values": findings["day_7_retention"]},
        ]

    def funnel(self, start_date: date | None, end_date: date | None) -> list[dict[str, Any]]:
        start, end = self._validate_window(start_date, end_date)
        return [
            {
                "date": row["session_start_date"],
                "channel_source": row["first_event_source"],
                "channel_medium": row["first_event_medium"],
                "measured_sessions": int(row["measured_sessions"]),
                "views": int(row["views"]),
                "engaged_sessions": int(row["engaged_sessions"]),
                "add_to_carts": int(row["add_to_carts"]),
                "checkouts": int(row["checkouts"]),
                "purchases": int(row["purchases"]),
            }
            for row in self._repository.funnel
            if start <= date.fromisoformat(row["session_start_date"]) <= end
            and ".safeframe." not in row["first_event_source"]
        ]

    def cohorts(self, start_date: date | None, end_date: date | None) -> list[dict[str, Any]]:
        start, end = self._validate_window(start_date, end_date)
        return [
            {
                "cohort_date": row["cohort_date"],
                "activity_date": row["activity_date"],
                "days_since_acquisition": int(row["days_since_acquisition"]),
                "cohort_users": int(row["cohort_users"]),
                "retained_users": int(row["retained_users"]),
                "measured_sessions": int(row["measured_sessions"]),
                "cohort_definition": row["cohort_definition"],
            }
            for row in self._repository.cohorts
            if start <= date.fromisoformat(row["activity_date"]) <= end
        ]

    def attribution(self) -> list[dict[str, Any]]:
        attribution = self._repository.findings["attribution"]
        return [
            {
                "model": model,
                "conversion_credit_total": float(attribution["credit_totals"][model]),
                "top_channel_credits": {
                    channel: float(credit)
                    for channel, credit in sorted(
                        attribution["all_channel_credits"][model].items(),
                        key=lambda item: (-item[1], item[0]),
                    )[:5]
                },
                "interpretation": attribution["interpretation"],
            }
            for model in ("first_touch", "last_touch", "linear", "time_decay")
        ]

    def audience_quality(self) -> list[dict[str, Any]]:
        records = simulate_integration_records()
        total = len(records)
        eligible = int(records["consent_eligible"].sum())
        matched = int((records["consent_eligible"] & records["partner_matched"]).sum())
        delivered = int(records["delivery_success"].sum())
        return [
            self._rate("consent_eligible_candidates", eligible, total),
            self._rate("partner_matched_candidates", matched, eligible),
            self._rate("delivery_success_candidates", delivered, matched),
        ]

    def integration_health(self) -> list[dict[str, Any]]:
        return [
            {
                "metric": str(row.metric),
                "numerator": int(str(row.numerator)),
                "denominator": int(str(row.denominator)),
                "rate": float(str(row.rate)) if row.rate is not None else None,
            }
            for row in integration_health(simulate_integration_records()).itertuples(index=False)
        ]

    def conversion_model(self) -> dict[str, Any]:
        return {
            "selected_model": "logistic_regression",
            "evaluation_population": "7,245 held-out identifier-free public-sample sessions",
            "metrics": {
                "no_skill_held_out": {"roc_auc": 0.5, "pr_auc": 0.013941, "brier_score": 0.013748},
                "logistic_regression_training_cv": {"roc_auc": 0.707922, "pr_auc": 0.043843, "brier_score": 0.012284},
                "logistic_regression_held_out": {"roc_auc": 0.652281, "pr_auc": 0.041429, "brier_score": 0.013582},
                "random_forest_held_out": {"roc_auc": 0.62904, "pr_auc": 0.040626, "brier_score": 0.08539},
            },
            "selected_threshold": 0.035589,
            "threshold_label": "capacity_50_per_1000_sessions",
        }

    def budget_scenario(
        self,
        total_budget: Decimal,
        minimums: dict[str, Decimal],
        capacities: dict[str, Decimal],
        expected_incremental_value: dict[str, Decimal],
    ) -> dict[str, Any]:
        self._validate_budget_channels(minimums, capacities, expected_incremental_value)
        try:
            inputs = BudgetInputs(
                total_budget=total_budget,
                minimums=minimums,
                capacities=capacities,
                expected_incremental_value=expected_incremental_value,
            )
            scenario = optimize_budget(inputs)
            sensitivity = scenario_sensitivity(inputs)
        except ValueError as error:
            raise APIValidationError(
                "invalid_budget_scenario",
                "Budget scenario is invalid",
                {"reason": str(error)},
            ) from error
        return {
            "allocations": {name: float(amount) for name, amount in scenario.allocations.items()},
            "total_budget": scenario.total_budget,
            "estimated_incremental_value": scenario.estimated_incremental_value,
            "assumptions": list(scenario.assumptions),
            "sensitivity": [
                {
                    "scenario": str(row.scenario),
                    "varied_channel": str(row.varied_channel),
                    "value_multiplier": float(str(row.value_multiplier)),
                    "estimated_incremental_value": float(
                        str(row.estimated_incremental_value)
                    ),
                    "ranking_changed_from_baseline": bool(row.ranking_changed_from_baseline),
                    "allocation_changed_from_baseline": bool(row.allocation_changed_from_baseline),
                    "decision_summary": str(row.decision_summary),
                }
                for row in sensitivity.itertuples(index=False)
            ],
            "robustness_summary": str(sensitivity.attrs["robustness_summary"]),
        }

    def _validate_window(
        self, start_date: date | None, end_date: date | None
    ) -> tuple[date, date]:
        start = start_date or MIN_DATE
        end = end_date or MAX_DATE
        if start < MIN_DATE or end > MAX_DATE or start > end:
            raise APIValidationError(
                "invalid_date_window",
                "Dates must be ordered and within the published source window",
                {"minimum": MIN_DATE.isoformat(), "maximum": MAX_DATE.isoformat()},
            )
        return start, end

    def _validate_budget_channels(
        self,
        minimums: dict[str, Decimal],
        capacities: dict[str, Decimal],
        expected_incremental_value: dict[str, Decimal],
    ) -> None:
        supplied = set(minimums) | set(capacities) | set(expected_incremental_value)
        unknown = sorted(supplied.difference(SUPPORTED_BUDGET_CHANNELS))
        if unknown:
            raise APIValidationError(
                "unknown_budget_channel",
                "Budget scenario contains an unsupported channel",
                {"supported_channels": sorted(SUPPORTED_BUDGET_CHANNELS)},
            )
        if not (set(minimums) == set(capacities) == set(expected_incremental_value)):
            raise APIValidationError(
                "mismatched_budget_channels",
                "Minimums, capacities, and expected values must use identical channels",
                {"fields": ["minimums", "capacities", "expected_incremental_value"]},
            )

    @staticmethod
    def _rate(metric: str, numerator: int, denominator: int) -> dict[str, Any]:
        return {
            "metric": metric,
            "numerator": numerator,
            "denominator": denominator,
            "rate": numerator / denominator if denominator else None,
        }
