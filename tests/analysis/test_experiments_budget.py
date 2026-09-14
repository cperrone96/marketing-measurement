"""Tests for deterministic synthetic A/B and budget decision scenarios."""

from __future__ import annotations

from decimal import Decimal

import pytest

from marketing_measurement.analysis.budget import (
    BudgetInputs,
    BudgetScenario,
    optimize_budget,
    scenario_sensitivity,
)
from marketing_measurement.analysis.experiments import (
    ExperimentDesign,
    analyze_experiment,
)
from marketing_measurement.simulation.integration import simulate_integration_records


@pytest.fixture
def solution() -> BudgetScenario:
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
    assert result.analysis_population == (
        "all randomized synthetic audience candidates (intent-to-treat)"
    )
    assert result.confidence_interval[0] <= result.itt_effect <= result.confidence_interval[1]
    assert result.conclusion.startswith("inconclusive")
    assert not result.meets_sample_size_gate
    assert result.design.baseline_rate == pytest.approx(0.062376)
    assert result.design.minimum_detectable_effect == pytest.approx(0.015594)
    assert result.design.planned_sample_per_arm == 4209
    assert "marginal" in result.design.hypothesis.lower()


def test_budget_obeys_total_and_channel_bounds(solution: BudgetScenario) -> None:
    assert solution.allocations.sum() == pytest.approx(solution.total_budget)
    assert (solution.allocations >= solution.minimums).all()
    assert (solution.allocations <= solution.capacities).all()


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


def test_nondefault_alpha_and_power_change_sample_size_and_confidence_interval() -> None:
    records = simulate_integration_records(200)
    default = analyze_experiment(records)
    alpha_only = analyze_experiment(records, ExperimentDesign(alpha=0.10))
    custom = analyze_experiment(records, ExperimentDesign(alpha=0.10, target_power=0.90))

    default_width = default.confidence_interval[1] - default.confidence_interval[0]
    alpha_only_width = alpha_only.confidence_interval[1] - alpha_only.confidence_interval[0]
    assert alpha_only.confidence_level == pytest.approx(0.90)
    assert alpha_only_width < default_width
    assert custom.design.planned_sample_per_arm > default.design.planned_sample_per_arm


@pytest.mark.parametrize(
    ("field", "value"),
    [("alpha", 0.0), ("target_power", 1.0), ("baseline_rate", 1.0)],
)
def test_experiment_design_rejects_invalid_probability_domains(field: str, value: float) -> None:
    with pytest.raises(ValueError, match=field):
        ExperimentDesign(**{field: value})


@pytest.mark.parametrize(
    "inputs",
    [
        BudgetInputs(
            total_budget=100.001,
            minimums={"channel_aurora": 0.0},
            capacities={"channel_aurora": 200.0},
            expected_incremental_value={"channel_aurora": 1.0},
        ),
        BudgetInputs(
            total_budget=100.0,
            minimums={"channel_aurora": 0.001},
            capacities={"channel_aurora": 200.0},
            expected_incremental_value={"channel_aurora": 1.0},
        ),
        BudgetInputs(
            total_budget=100.0,
            minimums={"channel_aurora": 0.0},
            capacities={"channel_aurora": 100.001},
            expected_incremental_value={"channel_aurora": 1.0},
        ),
    ],
)
def test_budget_rejects_subcent_inputs_before_feasibility(inputs: BudgetInputs) -> None:
    with pytest.raises(ValueError, match="whole cents"):
        optimize_budget(inputs)


def test_budget_returns_normalized_cent_values() -> None:
    result = optimize_budget(
        BudgetInputs(
            total_budget="1.00",
            minimums={"channel_aurora": "0.10", "channel_birch": "0.20"},
            capacities={"channel_aurora": "0.70", "channel_birch": "0.80"},
            expected_incremental_value={"channel_aurora": 1.4, "channel_birch": 1.1},
        )
    )
    assert result.total_budget == 1.00
    assert result.minimums.to_dict() == {
        "channel_aurora": Decimal("0.10"),
        "channel_birch": Decimal("0.20"),
    }
    assert result.capacities.to_dict() == {
        "channel_aurora": Decimal("0.70"),
        "channel_birch": Decimal("0.80"),
    }
    assert result.allocations.to_dict() == {
        "channel_aurora": Decimal("0.70"),
        "channel_birch": Decimal("0.30"),
    }


def test_channel_specific_sensitivity_detects_ranking_crossover_and_allocation_change() -> None:
    inputs = BudgetInputs(
        total_budget=100.0,
        minimums={"channel_aurora": 0.0, "channel_birch": 0.0},
        capacities={"channel_aurora": 100.0, "channel_birch": 100.0},
        expected_incremental_value={"channel_aurora": 1.0, "channel_birch": 0.9},
    )
    result = scenario_sensitivity(inputs)
    crossover = result.loc[result["scenario"] == "channel_aurora_down_20pct"].iloc[0]

    assert result["scenario"].tolist() == [
        "baseline",
        "channel_aurora_down_20pct",
        "channel_aurora_up_20pct",
        "channel_birch_down_20pct",
        "channel_birch_up_20pct",
    ]
    assert bool(crossover["ranking_changed_from_baseline"])
    assert bool(crossover["allocation_changed_from_baseline"])
    assert "channel_aurora=0.00-100.00" in result.attrs["robustness_summary"]
    assert "decision changes" in result.attrs["robustness_summary"]
    assert set(result["evidence_type"]) == {"synthetic"}
