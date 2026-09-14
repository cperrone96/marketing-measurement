"""Privacy-safe deterministic integration records for demonstrations only.

This module deliberately has no readers or writers for public-observed artifacts.
Its rows use pseudonymous keys, reserved example domains, and the ``synthetic``
evidence type so they cannot be mistaken for campaign or customer data.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

SYNTHETIC_SEED = 20260910
_EVIDENCE_TYPE = "synthetic"
_PARTNERS = ("partner_aurora", "partner_birch")
_DOMAINS = ("aurora.example", "birch.example")


def simulate_integration_records(
    rows: int = 200, *, seed: int = SYNTHETIC_SEED
) -> pd.DataFrame:
    """Create deterministic, non-identifying integration demonstration records.

    ``rows`` must be even because the experiment assignment is exactly 50/50.
    The generated keys cannot be joined to direct identifiers and are valid only
    within this synthetic fixture namespace.
    """
    if rows <= 0 or rows % 2:
        raise ValueError("rows must be a positive even number for 50/50 assignment")

    generator = np.random.default_rng(seed)
    record_numbers = np.arange(rows)
    consent_eligible = generator.random(rows) < 0.86
    partner_matched = consent_eligible & (generator.random(rows) < 0.81)
    delivery_attempted = partner_matched
    delivery_success = delivery_attempted & (generator.random(rows) < 0.91)
    rejection_reason = [
        "consent_ineligible"
        if not consent
        else "partner_unmatched"
        if not matched
        else "delivery_rejected"
        if attempted and not success
        else None
        for consent, matched, attempted, success in zip(
            consent_eligible,
            partner_matched,
            delivery_attempted,
            delivery_success,
            strict=True,
        )
    ]
    assignment = _balanced_assignment(rows, generator)
    message_variant = np.where(assignment == "treatment", "benefit_focused", "plain")
    exposure = delivery_success & (generator.random(rows) < 0.82)
    conversion_probability = np.where(assignment == "treatment", 0.15, 0.12)
    outcome_conversion = exposure & (generator.random(rows) < conversion_probability)
    outcome_click = exposure & (generator.random(rows) < np.where(assignment == "treatment", 0.36, 0.34))
    guardrail_opt_out = delivery_success & (generator.random(rows) < 0.012)

    return pd.DataFrame(
        {
            "synthetic_subject_key": [
                _pseudonymous_key(seed, int(value)) for value in record_numbers
            ],
            "evidence_type": _EVIDENCE_TYPE,
            "partner_label": np.take(_PARTNERS, record_numbers % len(_PARTNERS)),
            "partner_domain": np.take(_DOMAINS, record_numbers % len(_DOMAINS)),
            "consent_eligible": consent_eligible,
            "partner_matched": partner_matched,
            "delivery_attempted": delivery_attempted,
            "delivery_success": delivery_success,
            "rejection_reason": rejection_reason,
            "source_freshness_hours": generator.integers(1, 49, size=rows),
            "delivery_latency_minutes": generator.integers(5, 181, size=rows),
            "exposure": exposure,
            "cost_usd": np.round(generator.uniform(0.15, 1.25, size=rows), 2),
            "experiment_assignment": assignment,
            "message_variant": message_variant,
            "outcome_conversion": outcome_conversion,
            "outcome_click": outcome_click,
            "guardrail_opt_out": guardrail_opt_out,
        }
    )


def integration_health(records: pd.DataFrame) -> pd.DataFrame:
    """Calculate traceable synthetic integration-health rates.

    Every metric exposes its exact numerator and denominator.  Observed or mixed
    evidence is rejected instead of being silently co-mingled with this demo.
    """
    _require_synthetic(records)
    _require_columns(
        records,
        {
            "consent_eligible",
            "partner_matched",
            "delivery_success",
            "rejection_reason",
            "source_freshness_hours",
            "delivery_latency_minutes",
            "exposure",
        },
    )
    eligible = records["consent_eligible"].astype(bool)
    matched = records["partner_matched"].astype(bool)
    delivered = records["delivery_success"].astype(bool)
    rejected = records["rejection_reason"].notna()
    fresh = records["source_freshness_hours"].le(24)
    low_latency = records["delivery_latency_minutes"].le(60)
    exposed = records["exposure"].astype(bool)

    measures = (
        ("consent_eligibility", eligible, pd.Series(True, index=records.index)),
        ("partner_match_rate", eligible & matched, eligible),
        ("delivery_success_rate", eligible & matched & delivered, eligible & matched),
        ("rejection_rate", rejected, pd.Series(True, index=records.index)),
        ("freshness_sla_rate", fresh, pd.Series(True, index=records.index)),
        ("latency_sla_rate", delivered & low_latency, delivered),
        ("activation_rate", delivered & exposed, delivered),
    )
    values: list[dict[str, object]] = []
    for metric, numerator_mask, denominator_mask in measures:
        numerator = int(numerator_mask.sum())
        denominator = int(denominator_mask.sum())
        values.append(
            {
                "metric": metric,
                "numerator": numerator,
                "denominator": denominator,
                "rate": numerator / denominator if denominator else None,
                "evidence_type": _EVIDENCE_TYPE,
            }
        )
    return pd.DataFrame(values)


def _balanced_assignment(rows: int, generator: np.random.Generator) -> np.ndarray:
    """Shuffle a fixed equal-sized assignment vector without probability drift."""
    assignment = np.array(["control"] * (rows // 2) + ["treatment"] * (rows // 2))
    return generator.permutation(assignment)


def _pseudonymous_key(seed: int, record_number: int) -> str:
    material = f"synthetic-integration:{seed}:{record_number}".encode()
    return f"syn_{hashlib.sha256(material).hexdigest()[:20]}"


def _require_synthetic(records: pd.DataFrame) -> None:
    if "evidence_type" not in records.columns or set(records["evidence_type"]) != {
        _EVIDENCE_TYPE
    }:
        raise ValueError("integration health accepts only evidence_type='synthetic' rows")


def _require_columns(records: pd.DataFrame, required: set[str]) -> None:
    missing = required.difference(records.columns)
    if missing:
        raise ValueError(f"records is missing required columns: {sorted(missing)}")
