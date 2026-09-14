"""Tests for the isolated, deterministic synthetic integration fixture."""

from __future__ import annotations

import pandas as pd
import pytest

from marketing_measurement.simulation.integration import (
    SYNTHETIC_SEED,
    integration_health,
    simulate_integration_records,
)


@pytest.fixture
def simulated_frame() -> pd.DataFrame:
    return simulate_integration_records(200, seed=SYNTHETIC_SEED)


def test_simulated_rows_are_labeled(simulated_frame: pd.DataFrame) -> None:
    assert set(simulated_frame["evidence_type"]) == {"synthetic"}
    assert all(value.endswith(".example") for value in simulated_frame["partner_domain"])
    assert "subject_id" not in simulated_frame.columns


def test_simulation_is_byte_identical_for_the_same_seed() -> None:
    first = simulate_integration_records(20, seed=SYNTHETIC_SEED).to_csv(index=False)
    second = simulate_integration_records(20, seed=SYNTHETIC_SEED).to_csv(index=False)
    assert first == second


def test_integration_health_has_explicit_inputs(simulated_frame: pd.DataFrame) -> None:
    health = integration_health(simulated_frame)
    required = {
        "consent_eligibility",
        "partner_match_rate",
        "delivery_success_rate",
        "rejection_rate",
        "freshness_sla_rate",
        "latency_sla_rate",
        "activation_rate",
    }
    assert required == set(health["metric"])
    assert (health["denominator"] > 0).all()
    assert set(health["evidence_type"]) == {"synthetic"}


def test_observed_rows_cannot_be_used_for_synthetic_health() -> None:
    frame = simulate_integration_records(4)
    frame.loc[0, "evidence_type"] = "observed"
    with pytest.raises(ValueError, match="synthetic"):
        integration_health(frame)
