"""Deterministic synthetic budget allocation under cent-level constraints."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import pandas as pd

_EVIDENCE_TYPE = "synthetic"
_CENT = Decimal("0.01")
type Money = Decimal | int | float | str


@dataclass(frozen=True)
class BudgetInputs:
    """Assumptions required for a constrained, simulated allocation decision."""

    total_budget: Money
    minimums: Mapping[str, Money]
    capacities: Mapping[str, Money]
    expected_incremental_value: Mapping[str, Money]


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


@dataclass(frozen=True)
class _NormalizedBudgetInputs:
    channels: tuple[str, ...]
    total_cents: int
    minimum_cents: dict[str, int]
    capacity_cents: dict[str, int]
    expected_values: dict[str, Decimal]


def optimize_budget(inputs: BudgetInputs) -> BudgetScenario:
    """Maximize synthetic value after validating all money as exact whole cents."""
    return _optimize_normalized(_normalize_inputs(inputs))


def scenario_sensitivity(inputs: BudgetInputs) -> pd.DataFrame:
    """Test each channel independently at bounded -20% and +20% value changes.

    The output reports ranking/allocation changes and a robustness range. Values
    are synthetic assumptions, so the result is not a causal forecast.
    """
    normalized = _normalize_inputs(inputs)
    baseline = _optimize_normalized(normalized)
    baseline_ranking = _ranking(normalized.expected_values)
    scenarios: list[tuple[str, str, Decimal, BudgetScenario, tuple[str, ...]]] = [
        ("baseline", "baseline", Decimal(1), baseline, baseline_ranking)
    ]
    for channel in normalized.channels:
        for multiplier, direction in (
            (Decimal("0.8"), "down_20pct"),
            (Decimal("1.2"), "up_20pct"),
        ):
            adjusted_values = dict(normalized.expected_values)
            adjusted_values[channel] *= multiplier
            adjusted = _NormalizedBudgetInputs(
                channels=normalized.channels,
                total_cents=normalized.total_cents,
                minimum_cents=normalized.minimum_cents,
                capacity_cents=normalized.capacity_cents,
                expected_values=adjusted_values,
            )
            scenarios.append(
                (
                    f"{channel}_{direction}",
                    channel,
                    multiplier,
                    _optimize_normalized(adjusted),
                    _ranking(adjusted_values),
                )
            )

    rows: list[dict[str, object]] = []
    allocation_history: dict[str, list[float]] = {
        channel: [] for channel in normalized.channels
    }
    for name, channel, multiplier, scenario, ranking in scenarios:
        allocation_changed = not scenario.allocations.equals(baseline.allocations)
        for allocated_channel, amount in scenario.allocations.items():
            allocation_history[str(allocated_channel)].append(float(amount))
        rows.append(
            {
                "scenario": name,
                "varied_channel": channel,
                "value_multiplier": float(multiplier),
                "estimated_incremental_value": scenario.estimated_incremental_value,
                "allocation_summary": _allocation_summary(scenario.allocations),
                "ranking_changed_from_baseline": ranking != baseline_ranking,
                "allocation_changed_from_baseline": allocation_changed,
                "decision_summary": (
                    "synthetic allocation changes under this bounded assumption"
                    if allocation_changed
                    else "synthetic allocation remains unchanged under this bounded assumption"
                ),
                "evidence_type": _EVIDENCE_TYPE,
            }
        )
    result = pd.DataFrame(rows)
    changes = int(result["allocation_changed_from_baseline"].sum())
    ranges = "; ".join(
        f"{channel}={min(amounts):.2f}-{max(amounts):.2f}"
        for channel, amounts in allocation_history.items()
    )
    result.attrs["robustness_summary"] = (
        f"Synthetic allocation ranges: {ranges}; decision changes in {changes} of "
        f"{len(result) - 1} channel-specific perturbations."
    )
    return result


def _normalize_inputs(inputs: BudgetInputs) -> _NormalizedBudgetInputs:
    channels = tuple(sorted(inputs.minimums))
    if not channels:
        raise ValueError("at least one channel is required")
    if (
        set(inputs.capacities) != set(channels)
        or set(inputs.expected_incremental_value) != set(channels)
    ):
        raise ValueError("minimums, capacities, and expected values must use identical channels")
    total_cents = _money_to_cents(inputs.total_budget, "total_budget")
    minimum_cents = {
        channel: _money_to_cents(inputs.minimums[channel], f"minimums[{channel!r}]")
        for channel in channels
    }
    capacity_cents = {
        channel: _money_to_cents(inputs.capacities[channel], f"capacities[{channel!r}]")
        for channel in channels
    }
    expected_values = {
        channel: _non_negative_decimal(
            inputs.expected_incremental_value[channel],
            f"expected_incremental_value[{channel!r}]",
        )
        for channel in channels
    }
    if total_cents < 0 or any(value < 0 for value in minimum_cents.values()) or any(
        value < 0 for value in capacity_cents.values()
    ):
        raise ValueError("total_budget, minimums, and capacities must be non-negative")
    if any(minimum_cents[channel] > capacity_cents[channel] for channel in channels):
        raise ValueError("channel minimum cannot exceed its capacity")
    if sum(minimum_cents.values()) > total_cents:
        raise ValueError("total_budget cannot be below the sum of channel minimums")
    if sum(capacity_cents.values()) < total_cents:
        raise ValueError("total_budget exceeds aggregate channel capacity")
    return _NormalizedBudgetInputs(
        channels=channels,
        total_cents=total_cents,
        minimum_cents=minimum_cents,
        capacity_cents=capacity_cents,
        expected_values=expected_values,
    )


def _optimize_normalized(inputs: _NormalizedBudgetInputs) -> BudgetScenario:
    allocations_cents = dict(inputs.minimum_cents)
    remaining = inputs.total_cents - sum(allocations_cents.values())
    for channel in _ranking(inputs.expected_values):
        additional_capacity = inputs.capacity_cents[channel] - allocations_cents[channel]
        added = min(remaining, additional_capacity)
        allocations_cents[channel] += added
        remaining -= added
    if remaining:
        raise RuntimeError("budget optimizer could not allocate the complete budget")
    allocations = _money_series(allocations_cents)
    minimums = _money_series(inputs.minimum_cents)
    capacities = _money_series(inputs.capacity_cents)
    estimated_value = sum(
        (
            (Decimal(allocations_cents[channel]) / 100)
            * inputs.expected_values[channel]
            for channel in inputs.channels
        ),
        Decimal(0),
    ).quantize(_CENT, rounding=ROUND_HALF_UP)
    return BudgetScenario(
        allocations=allocations,
        total_budget=_from_cents(inputs.total_cents),
        minimums=minimums,
        capacities=capacities,
        expected_incremental_value=pd.Series(
            {channel: float(inputs.expected_values[channel]) for channel in inputs.channels},
            dtype=float,
        ),
        estimated_incremental_value=float(estimated_value),
        assumptions=(
            "Synthetic scenario only; expected incremental value is an input assumption.",
            "Money inputs are validated as exact whole cents before feasibility checks.",
            "Sensitivity reports bounded decision changes and ranges, not causal forecasts.",
        ),
    )


def _money_to_cents(value: Money, name: str) -> int:
    decimal_value = _non_negative_decimal(value, name, allow_negative=True)
    cents = decimal_value * 100
    if cents != cents.to_integral_value():
        raise ValueError(f"{name} must be specified in whole cents")
    return int(cents)


def _non_negative_decimal(
    value: Money, name: str, *, allow_negative: bool = False
) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not decimal_value.is_finite():
        raise ValueError(f"{name} must be a finite number")
    if not allow_negative and decimal_value < 0:
        raise ValueError(f"{name} must be non-negative")
    return decimal_value


def _money_series(amounts_cents: Mapping[str, int]) -> pd.Series:
    return pd.Series(
        {channel: _from_cents(amount) for channel, amount in amounts_cents.items()},
        dtype=float,
    )


def _from_cents(value: int) -> float:
    return float(Decimal(value) / 100)


def _ranking(values: Mapping[str, Decimal]) -> tuple[str, ...]:
    return tuple(sorted(values, key=lambda channel: (-values[channel], channel)))


def _allocation_summary(allocations: pd.Series) -> str:
    return "; ".join(f"{channel}={amount:.2f}" for channel, amount in allocations.items())
