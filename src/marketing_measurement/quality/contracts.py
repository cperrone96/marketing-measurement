"""Normalization and validation contract for exported GA4 event rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from typing import Any, cast

import pandas as pd

DOCUMENTED_COVERAGE_START = datetime(2020, 11, 1, tzinfo=UTC)
DOCUMENTED_COVERAGE_END = datetime(2021, 2, 1, tzinfo=UTC)

_ECOMMERCE_NUMERIC_FIELDS = frozenset(
    {
        "purchase_revenue",
        "purchase_revenue_in_usd",
        "refund_value",
        "refund_value_in_usd",
        "shipping_value",
        "shipping_value_in_usd",
        "tax_value",
        "tax_value_in_usd",
        "total_item_quantity",
        "unique_items",
    }
)
_REVENUE_FIELDS = frozenset(
    {
        "purchase_revenue",
        "purchase_revenue_in_usd",
        "refund_value",
        "refund_value_in_usd",
    }
)


@dataclass(frozen=True)
class ValidationReport:
    """Normalized valid events and original-identity-preserving quarantined events."""

    valid: pd.DataFrame
    quarantine: pd.DataFrame

    @property
    def valid_count(self) -> int:
        return len(self.valid)

    @property
    def quarantine_count(self) -> int:
        return len(self.quarantine)


def validate_ga4_events(frame: pd.DataFrame) -> ValidationReport:
    """Normalize nested GA4 fields and quarantine contract violations.

    Missing source values remain ``None``/``pd.NA``; this boundary never invents a
    zero quantity or revenue. A quarantined event receives all detected reasons and
    the first reason in a fixed priority order as its deterministic primary reason.
    """
    normalized = _normalize_ga4_events(frame)
    valid_rows: list[dict[str, Any]] = []
    quarantined_rows: list[dict[str, Any]] = []

    for raw_row in normalized.to_dict(orient="records"):
        row = cast(dict[str, Any], raw_row)
        reasons = _validation_reasons(row)
        if reasons:
            row["reason"] = reasons[0]
            row["reasons"] = reasons
            quarantined_rows.append(row)
        else:
            valid_rows.append(row)

    return ValidationReport(
        valid=pd.DataFrame(valid_rows, columns=normalized.columns),
        quarantine=pd.DataFrame(
            quarantined_rows, columns=[*normalized.columns, "reason", "reasons"]
        ),
    )


def _normalize_ga4_events(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    if "source_row_id" not in normalized.columns:
        normalized.insert(0, "source_row_id", list(normalized.index))

    for column in ("event_params", "items", "traffic_source", "device", "geo", "ecommerce", "privacy_info"):
        if column not in normalized.columns:
            normalized[column] = None

    normalized["event_params"] = normalized["event_params"].map(_normalize_event_params)
    normalized["items"] = normalized["items"].map(_normalize_items)
    for field in ("traffic_source", "device", "geo", "privacy_info"):
        normalized[field] = normalized[field].map(_normalize_mapping)
        normalized = _add_nested_columns(normalized, field)

    normalized["ecommerce"] = normalized["ecommerce"].map(_normalize_ecommerce)
    normalized = _add_nested_columns(normalized, "ecommerce")
    return normalized


def _normalize_event_params(value: Any) -> dict[str, Any] | None:
    if _is_missing(value):
        return None
    if isinstance(value, dict):
        # Already-normalized fixtures are permitted and retain their source values.
        return dict(value)
    if not isinstance(value, list):
        return None

    params: dict[str, Any] = {}
    for parameter in value:
        if not isinstance(parameter, dict):
            continue
        key = parameter.get("key")
        if not isinstance(key, str) or not key:
            continue
        raw_value = parameter.get("value")
        params[key] = _ga4_parameter_value(raw_value)
    return params


def _ga4_parameter_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in ("string_value", "int_value", "double_value", "float_value"):
        if key not in value or _is_missing(value[key]):
            continue
        if key == "string_value":
            return value[key]
        return _number_or_none(value[key])
    return None


def _normalize_items(value: Any) -> list[dict[str, Any]] | None:
    if _is_missing(value):
        return None
    if not isinstance(value, list):
        return None
    items: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            items.append({"_malformed_item": item})
            continue
        normalized_item = dict(item)
        for field in ("quantity", "price", "item_revenue", "item_revenue_in_usd"):
            if field in normalized_item:
                normalized_item[field] = _number_or_none(normalized_item[field])
        items.append(normalized_item)
    return items


def _normalize_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return dict(value)


def _normalize_ecommerce(value: Any) -> dict[str, Any] | None:
    normalized = _normalize_mapping(value)
    if normalized is None:
        return None
    for field in _ECOMMERCE_NUMERIC_FIELDS:
        if field in normalized:
            normalized[field] = _number_or_none(normalized[field])
    return normalized


def _add_nested_columns(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    nested_keys = sorted(
        {
            key
            for value in frame[field]
            if isinstance(value, dict)
            for key in value
        }
    )
    for key in nested_keys:
        column = f"{field}_{key}"
        if column not in frame.columns:
            frame[column] = frame[field].map(_extract_nested_value_for_key(key))
    return frame


def _extract_nested_value_for_key(key: str) -> Callable[[Any], Any]:
    def extract(value: Any) -> Any:
        return value.get(key) if isinstance(value, dict) else None

    return extract


def _validation_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    event_time = _event_time(row.get("event_timestamp"))
    if event_time is None:
        reasons.append("event_timestamp_out_of_range")
    elif not DOCUMENTED_COVERAGE_START <= event_time < DOCUMENTED_COVERAGE_END:
        reasons.append("event_outside_documented_coverage")

    user_pseudo_id = row.get("user_pseudo_id")
    if not isinstance(user_pseudo_id, str) or not user_pseudo_id.strip():
        reasons.append("user_pseudo_id_malformed")
    event_name = row.get("event_name")
    if not isinstance(event_name, str) or not event_name.strip():
        reasons.append("event_name_malformed")

    if _has_impossible_item_quantity(row.get("items")):
        reasons.append("item_quantity_invalid")
    if _has_negative_ecommerce_revenue(row.get("ecommerce")):
        reasons.append("ecommerce_revenue_negative")
    return reasons


def _event_time(value: Any) -> datetime | None:
    number = _number_or_none(value)
    if number is None or number <= 0:
        return None
    try:
        return datetime.fromtimestamp(number / 1_000_000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _has_impossible_item_quantity(items: Any) -> bool:
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, dict):
            return True
        if "quantity" not in item or _is_missing(item["quantity"]):
            continue
        quantity = _number_or_none(item["quantity"])
        if quantity is None or quantity <= 0:
            return True
    return False


def _has_negative_ecommerce_revenue(ecommerce: Any) -> bool:
    if not isinstance(ecommerce, dict):
        return False
    for field in _REVENUE_FIELDS:
        if field not in ecommerce or _is_missing(ecommerce[field]):
            continue
        value = _number_or_none(ecommerce[field])
        if value is None or value < 0:
            return True
    return False


def _number_or_none(value: Any) -> float | int | None:
    if _is_missing(value) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(missing)
    except ValueError:
        # ``pd.isna`` returns an array for containers; containers are not scalars.
        return False
