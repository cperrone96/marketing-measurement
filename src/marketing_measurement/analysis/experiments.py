"""Predeclared synthetic A/B analysis with an intent-to-treat estimate."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt

import pandas as pd

_EVIDENCE_TYPE = "synthetic"
_Z_ALPHA_TWO_SIDED = 1.959963984540054
_Z_POWER_80 = 0.8416212335729143


@dataclass(frozen=True)
class ExperimentDesign:
    """The single predeclared variable and its fixed decision gate."""

    hypothesis: str = (
        "For synthetic eligible subjects, benefit-focused message copy increases "
        "conversion rate versus plain message copy."
    )
    variable: str = "message_variant"
    primary_metric: str = "conversion_rate"
    secondary_metrics: tuple[str, ...] = ("click_rate",)
    guardrail_metrics: tuple[str, ...] = ("opt_out_rate",)
    alpha: float = 0.05
    target_power: float = 0.80
    baseline_rate: float = 0.12
    minimum_detectable_effect: float = 0.03

    @property
    def planned_sample_per_arm(self) -> int:
        """Normal-approximation sample size for a two-sided proportion test."""
        treatment_rate = self.baseline_rate + self.minimum_detectable_effect
        variance = self.baseline_rate * (1 - self.baseline_rate) + treatment_rate * (
            1 - treatment_rate
        )
        z_total = _Z_ALPHA_TWO_SIDED + _Z_POWER_80
        return ceil((z_total**2 * variance) / self.minimum_detectable_effect**2)


@dataclass(frozen=True)
class ExperimentResult:
    """A traceable analysis result; this is not a campaign-performance claim."""

    design: ExperimentDesign
    assignment_counts: dict[str, int]
    balance_checks: dict[str, float]
    analysis_population: str
    primary_metric: str
    itt_effect: float
    confidence_interval: tuple[float, float]
    secondary_metric_effects: dict[str, float]
    guardrail_metric_effects: dict[str, float]
    meets_sample_size_gate: bool
    conclusion: str
    evidence_type: str = _EVIDENCE_TYPE


def analyze_experiment(
    records: pd.DataFrame, design: ExperimentDesign | None = None
) -> ExperimentResult:
    """Estimate treatment-minus-control under fixed 50/50 intent-to-treat rules.

    The calculation never filters on delivery, exposure, or outcome.  When the
    predeclared sample-size gate is unmet, it reports an inconclusive synthetic
    demonstration and does not promote either arm as a winner.
    """
    design = design or ExperimentDesign()
    _validate_experiment_records(records)
    counts = records["experiment_assignment"].value_counts().to_dict()
    control_count = int(counts.get("control", 0))
    treatment_count = int(counts.get("treatment", 0))
    if control_count != treatment_count:
        raise ValueError("experiment assignment must be exactly 50/50")

    control = records.loc[records["experiment_assignment"] == "control"]
    treatment = records.loc[records["experiment_assignment"] == "treatment"]
    itt_effect, confidence_interval = _difference_with_ci(
        treatment["outcome_conversion"], control["outcome_conversion"]
    )
    secondary, guardrails = _metric_effects(treatment, control)
    balance_checks = {
        "consent_eligibility_difference": float(
            treatment["consent_eligible"].mean() - control["consent_eligible"].mean()
        ),
        "partner_match_difference": float(
            treatment["partner_matched"].mean() - control["partner_matched"].mean()
        ),
        "mean_cost_difference_usd": float(
            treatment["cost_usd"].mean() - control["cost_usd"].mean()
        ),
    }
    meets_gate = min(control_count, treatment_count) >= design.planned_sample_per_arm
    conclusion = (
        "inconclusive synthetic demonstration: the predeclared sample-size gate "
        "was not met; no arm is declared a winner."
        if not meets_gate
        else "synthetic estimate meets the sample-size gate; interpretation remains simulated."
    )
    return ExperimentResult(
        design=design,
        assignment_counts={"control": control_count, "treatment": treatment_count},
        balance_checks=balance_checks,
        analysis_population="intent-to-treat",
        primary_metric=design.primary_metric,
        itt_effect=itt_effect,
        confidence_interval=confidence_interval,
        secondary_metric_effects=secondary,
        guardrail_metric_effects=guardrails,
        meets_sample_size_gate=meets_gate,
        conclusion=conclusion,
    )


def _difference_with_ci(
    treatment: pd.Series, control: pd.Series
) -> tuple[float, tuple[float, float]]:
    treatment_rate = float(treatment.astype(float).mean())
    control_rate = float(control.astype(float).mean())
    effect = treatment_rate - control_rate
    standard_error = sqrt(
        treatment_rate * (1 - treatment_rate) / len(treatment)
        + control_rate * (1 - control_rate) / len(control)
    )
    interval = (effect - _Z_ALPHA_TWO_SIDED * standard_error, effect + _Z_ALPHA_TWO_SIDED * standard_error)
    return effect, interval


def _metric_effects(
    treatment: pd.DataFrame, control: pd.DataFrame
) -> tuple[dict[str, float], dict[str, float]]:
    return (
        {"click_rate": float(treatment["outcome_click"].mean() - control["outcome_click"].mean())},
        {"opt_out_rate": float(treatment["guardrail_opt_out"].mean() - control["guardrail_opt_out"].mean())},
    )


def _validate_experiment_records(records: pd.DataFrame) -> None:
    required = {
        "evidence_type",
        "experiment_assignment",
        "consent_eligible",
        "partner_matched",
        "cost_usd",
        "outcome_conversion",
        "outcome_click",
        "guardrail_opt_out",
    }
    missing = required.difference(records.columns)
    if missing:
        raise ValueError(f"records is missing required columns: {sorted(missing)}")
    if set(records["evidence_type"]) != {_EVIDENCE_TYPE}:
        raise ValueError("experiment analysis accepts only evidence_type='synthetic' rows")
    if set(records["experiment_assignment"]) != {"control", "treatment"}:
        raise ValueError("experiment_assignment must contain control and treatment")
