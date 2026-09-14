"""Tests for deterministic synthetic A/B and budget decision scenarios."""

from __future__ import annotations

import pytest

from marketing_measurement.analysis.budget import (
    BudgetInputs,
    optimize_budget,
    scenario_sensitivity,
)
from marketing_measurement.analysis.experiments import analyze_experiment
from marketing_measurement.simulation.integration import simulate_integration_records


@pytest.fixture
def solution() -> object:
    inputs = BudgetInputs(
        total_budget=1_000.0,
        minimums={"channel_aurora": 200.0, "channel_birch": 100.0},
        capacities={"channel_aurora": 700.0, "channel_birch": 800.0},
        expected_incremental_value={"channel_aurora": 1.4, "channel_birch": 1.1},
    )
    return optimize_budget(inputs)


def test_experiment_uses_balanced_deterministic_intent_to_treat() -> None:
    result = analyze_experiment(simulate_integration_records(200))
    assert result.assignment_counts == {"control": 100, "treatment": 100}
    assert result.primary_metric == "conversion_rate"
    assert result.analysis_population == "intent-to-treat"
    assert result.confidence_interval[0] <= result.itt_effect <= result.confidence_interval[1]
    assert result.conclusion.startswith("inconclusive")
    assert not result.meets_sample_size_gate


def test_budget_obeys_total_and_channel_bounds(solution: object) -> None:
    assert solution.allocations.sum() == pytest.approx(solution.total_budget)  # type: ignore[attr-defined]
    assert (solution.allocations >= solution.minimums).all()  # type: ignore[attr-defined]
    assert (solution.allocations <= solution.capacities).all()  # type: ignore[attr-defined]


def test_budget_rejects_infeasible_or_nonpositive_constraints() -> None:
    with pytest.raises(ValueError, match="minimum"):
        optimize_budget(
            BudgetInputs(
                total_budget=100.0,
                minimums={"channel_aurora": 101.0},
                capacities={"channel_aurora": 200.0},
                expected_incremental_value={"channel_aurora": 1.0},
            )
        )


def test_sensitivity_is_deterministic_and_labeled() -> None:
    inputs = BudgetInputs(
        total_budget=500.0,
        minimums={"channel_aurora": 100.0, "channel_birch": 100.0},
        capacities={"channel_aurora": 400.0, "channel_birch": 400.0},
        expected_incremental_value={"channel_aurora": 1.3, "channel_birch": 1.1},
    )
    result = scenario_sensitivity(inputs, (0.8, 1.0, 1.2))
    assert result["assumption_multiplier"].tolist() == [0.8, 1.0, 1.2]
    assert set(result["evidence_type"]) == {"synthetic"}
