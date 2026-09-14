"""Service layer separating HTTP routes from reviewed artifact interpretation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from api.repository import ArtifactRepository
from marketing_measurement.analysis.budget import (
    BudgetInputs,
    optimize_budget,
    scenario_sensitivity,
)
from marketing_measurement.analysis.experiments import analyze_experiment
from marketing_measurement.simulation.integration import (
    SYNTHETIC_SEED,
    integration_health,
    simulate_integration_records,
)

MIN_DATE = date(2020, 11, 1)
MAX_DATE = date(2021, 1, 31)
SUPPORTED_BUDGET_CHANNELS = frozenset({"channel_aurora", "channel_birch"})
_CENT = Decimal("0.01")
_SYNTHETIC_GENERATORS = {
    "integration": (
        "deterministic integration generator",
        "src/marketing_measurement/simulation/integration.py",
    ),
    "budget": (
        "deterministic budget scenario generator",
        "src/marketing_measurement/analysis/budget.py",
    ),
}

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

    def artifact_sha256(self, relative_path: str) -> str:
        """Expose a reviewed-artifact digest without leaking filesystem paths."""
        return self._repository.source_sha256(relative_path)

    def synthetic_evidence(self, generator: str) -> dict[str, Any]:
        artifact, source_artifact = _SYNTHETIC_GENERATORS[generator]
        return {
            "evidence_type": "synthetic",
            "source_date_or_window": f"deterministic scenario seed {SYNTHETIC_SEED}",
            "provenance": {
                "artifact": artifact,
                "sha256": self._repository.source_sha256(source_artifact),
            },
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
                    "evidence": self.synthetic_evidence("integration"),
                },
            ],
        )

    def kpis(self) -> list[dict[str, Any]]:
        findings = self._repository.findings
        return [
            {"name": "funnel", "values": findings["funnel"]},
            {"name": "day_7_retention", "values": findings["day_7_retention"]},
        ]

    def portfolio_analyses(self) -> list[dict[str, Any]]:
        decisions = {
            "landing_page": "Compare landing-page quality before scaling acquisition.",
            "device": "Validate mobile journey quality alongside desktop volume.",
            "product_revenue": "Use revenue and product-view denominators together; do not rank on revenue alone.",
            "high_value_journey": "Investigate observed stage combinations before proposing a test.",
        }
        digest = self._repository.source_sha256(
            "data/observed/ga4_public_sample/portfolio_decision_aggregates.json"
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self._repository.portfolio_analyses:
            grouped[str(row["analysis"])].append(
                {key: value for key, value in row.items() if key != "analysis"}
            )
        return [
            {
                "analysis": analysis,
                "decision": decisions[analysis],
                "rows": grouped[analysis],
                "evidence": self.public_evidence(
                    "reviewed portfolio decision aggregates", digest
                ),
            }
            for analysis in (
                "landing_page",
                "device",
                "product_revenue",
                "high_value_journey",
            )
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
        ]

    def funnel_decision_summary(
        self, rows: Sequence[dict[str, Any]]
    ) -> dict[str, Any]:
        """Aggregate the complete filtered collection before HTTP pagination."""
        stage_fields = (
            "views",
            "engaged_sessions",
            "add_to_carts",
            "checkouts",
            "purchases",
        )
        stages = {field: sum(int(row[field]) for row in rows) for field in stage_fields}
        channels: dict[str, dict[str, int | str]] = defaultdict(
            lambda: {
                "channel": "",
                "views": 0,
                "engaged_sessions": 0,
                "purchases": 0,
            }
        )
        for row in rows:
            channel = f"{row['channel_source']} / {row['channel_medium']}"
            channels[channel]["channel"] = channel
            for field in ("views", "engaged_sessions", "purchases"):
                channels[channel][field] = int(channels[channel][field]) + int(
                    row[field]
                )
        ranked_channels = sorted(
            channels.values(),
            key=lambda item: (-int(item["engaged_sessions"]), str(item["channel"])),
        )[:8]
        return {
            "coverage": "full_filtered_window",
            "stages": stages,
            "channels": ranked_channels,
        }

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

    def cohort_decision_summary(
        self, rows: Sequence[dict[str, Any]]
    ) -> dict[str, Any]:
        """Publish complete day-7 retention evidence before HTTP pagination."""
        items = []
        for row in rows:
            if int(row["days_since_acquisition"]) != 7:
                continue
            cohort_users = int(row["cohort_users"])
            retained_users = int(row["retained_users"])
            items.append(
                {
                    "cohort_date": str(row["cohort_date"]),
                    "days_since_acquisition": 7,
                    "cohort_users": cohort_users,
                    "retained_users": retained_users,
                    "retention_rate": (
                        retained_users / cohort_users if cohort_users else None
                    ),
                }
            )
        return {"coverage": "complete_day_7_cohorts", "items": items}

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
        return self._repository.model_evaluation

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
            "allocations": {
                name: _money_string(amount)
                for name, amount in scenario.allocations.items()
            },
            "total_budget": _money_string(scenario.total_budget),
            "estimated_incremental_value": _money_string(
                scenario.estimated_incremental_value
            ),
            "assumptions": list(scenario.assumptions),
            "sensitivity": [
                {
                    "scenario": str(row.scenario),
                    "varied_channel": str(row.varied_channel),
                    "value_multiplier": float(str(row.value_multiplier)),
                    "estimated_incremental_value": _money_string(
                        Decimal(str(row.estimated_incremental_value))
                    ),
                    "ranking_changed_from_baseline": bool(row.ranking_changed_from_baseline),
                    "allocation_changed_from_baseline": bool(row.allocation_changed_from_baseline),
                    "decision_summary": str(row.decision_summary),
                }
                for row in sensitivity.itertuples(index=False)
            ],
            "robustness_summary": str(sensitivity.attrs["robustness_summary"]),
            "experiment": self.experiment_scenario(),
        }

    def experiment_scenario(self) -> dict[str, Any]:
        result = analyze_experiment(simulate_integration_records())
        return {
            "evidence_type": "synthetic",
            "analysis_population": result.analysis_population,
            "baseline_rate": result.design.baseline_rate,
            "minimum_detectable_effect": result.design.minimum_detectable_effect,
            "planned_sample_per_arm": result.design.planned_sample_per_arm,
            "observed_sample_per_arm": min(result.assignment_counts.values()),
            "itt_effect": result.itt_effect,
            "confidence_interval": result.confidence_interval,
            "confidence_level": result.confidence_level,
            "conclusion": result.conclusion,
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


def _money_string(value: Decimal) -> str:
    """Encode a cent-validated Task 6 output at a fixed two-decimal scale."""
    try:
        return format(value.quantize(_CENT), "f")
    except (InvalidOperation, OverflowError) as error:
        raise APIValidationError(
            "invalid_budget_scenario",
            "Budget scenario is invalid",
            {"reason": "monetary output exceeds supported precision"},
        ) from error
