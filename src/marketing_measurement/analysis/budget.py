"""Deterministic synthetic budget allocation under explicit hard constraints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

_EVIDENCE_TYPE = "synthetic"


@dataclass(frozen=True)
class BudgetInputs:
    """Assumptions required for a constrained, simulated allocation decision."""

    total_budget: float
    minimums: Mapping[str, float]
    capacities: Mapping[str, float]
    expected_incremental_value: Mapping[str, float]


@dataclass(frozen=True)
class BudgetScenario:
    """One deterministic allocation; figures are scenario assumptions, not forecasts."""

    allocations: pd.Series
    total_budget: float
    minimums: pd.Series
    capacities: pd.Series
    expected_incremental_value: pd.Series
    estimated_incremental_value: float
    assumptions: tuple[str, ...]
    evidence_type: str = _EVIDENCE_TYPE


def optimize_budget(inputs: BudgetInputs) -> BudgetScenario:
    """Maximize synthetic value by filling channels in value order within bounds.

    Currency is allocated in cents, so the returned allocation sums exactly to
    the supplied total when represented to two decimal places.
    """
    channels, minimums, capacities, values = _validated_series(inputs)
    allocations_cents = {channel: _to_cents(float(minimums[channel])) for channel in channels}
    remaining = _to_cents(inputs.total_budget) - sum(allocations_cents.values())
    for channel in sorted(channels, key=lambda name: (-float(values[name]), name)):
        additional_capacity = _to_cents(float(capacities[channel])) - allocations_cents[channel]
        add = min(remaining, additional_capacity)
        allocations_cents[channel] += add
        remaining -= add
    if remaining:
        raise RuntimeError("budget optimizer could not allocate the complete budget")

    allocations = pd.Series(
        {channel: allocations_cents[channel] / 100 for channel in channels}, dtype=float
    )
    estimated_value = round(float((allocations * values).sum()), 2)
    return BudgetScenario(
        allocations=allocations,
        total_budget=round(inputs.total_budget, 2),
        minimums=minimums,
        capacities=capacities,
        expected_incremental_value=values,
        estimated_incremental_value=estimated_value,
        assumptions=(
            "Synthetic scenario only; expected incremental value is an input assumption.",
            "Allocations are rounded to cents; estimated value is rounded to two decimals.",
            "No causal return, campaign performance, or customer outcome is asserted.",
        ),
    )


def scenario_sensitivity(
    inputs: BudgetInputs, multipliers: tuple[float, ...] = (0.8, 1.0, 1.2)
) -> pd.DataFrame:
    """Vary all value assumptions deterministically and report rounded scenarios."""
    if not multipliers or any(multiplier < 0 for multiplier in multipliers):
        raise ValueError("sensitivity multipliers must be non-negative and non-empty")
    rows: list[dict[str, object]] = []
    for multiplier in multipliers:
        scenario = BudgetInputs(
            total_budget=inputs.total_budget,
            minimums=inputs.minimums,
            capacities=inputs.capacities,
            expected_incremental_value={
                channel: value * multiplier
                for channel, value in inputs.expected_incremental_value.items()
            },
        )
        result = optimize_budget(scenario)
        rows.append(
            {
                "assumption_multiplier": multiplier,
                "estimated_incremental_value": result.estimated_incremental_value,
                "allocation_summary": "; ".join(
                    f"{channel}={amount:.2f}" for channel, amount in result.allocations.items()
                ),
                "evidence_type": _EVIDENCE_TYPE,
            }
        )
    return pd.DataFrame(rows)


def _validated_series(
    inputs: BudgetInputs,
) -> tuple[tuple[str, ...], pd.Series, pd.Series, pd.Series]:
    if inputs.total_budget < 0:
        raise ValueError("total_budget must be non-negative")
    channels = tuple(sorted(inputs.minimums))
    if not channels:
        raise ValueError("at least one channel is required")
    if set(inputs.capacities) != set(channels) or set(inputs.expected_incremental_value) != set(channels):
        raise ValueError("minimums, capacities, and expected values must use identical channels")
    minimums = pd.Series({channel: float(inputs.minimums[channel]) for channel in channels})
    capacities = pd.Series({channel: float(inputs.capacities[channel]) for channel in channels})
    values = pd.Series(
        {channel: float(inputs.expected_incremental_value[channel]) for channel in channels}
    )
    if (minimums < 0).any() or (capacities < 0).any() or (values < 0).any():
        raise ValueError("minimums, capacities, and expected values must be non-negative")
    if (minimums > capacities).any():
        raise ValueError("channel minimum cannot exceed its capacity")
    if float(minimums.sum()) > inputs.total_budget:
        raise ValueError("total_budget cannot be below the sum of channel minimums")
    if float(capacities.sum()) < inputs.total_budget:
        raise ValueError("total_budget exceeds aggregate channel capacity")
    return channels, minimums, capacities, values


def _to_cents(value: float) -> int:
    return round(value * 100)
