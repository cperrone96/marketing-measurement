"""Contract tests for the JSON/NDJSON GA4 export boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from marketing_measurement.ingestion.ga4 import load_ga4_export
from marketing_measurement.quality.contracts import validate_ga4_events


@pytest.fixture
def ga4_fixture() -> pd.DataFrame:
    """Small synthetic schema fixture; it is not observed Google data."""
    return pd.DataFrame(
        [
            {
                "event_timestamp": 1609459200000000,
                "event_name": "purchase",
                "user_pseudo_id": "fixture-user-001",
                "event_params": [
                    {"key": "ga_session_id", "value": {"int_value": "1001"}},
                    {"key": "currency", "value": {"string_value": "USD"}},
                ],
                "items": [{"item_id": "sku-001", "quantity": "2", "price": "19.50"}],
                "traffic_source": {"source": "google", "medium": "organic"},
                "device": {"category": "desktop"},
                "geo": {"country": "United States"},
                "ecommerce": {"purchase_revenue": "39.00", "transaction_id": "T-001"},
                "privacy_info": {"analytics_storage": "Yes"},
            },
            {
                "event_timestamp": 1609545600000000,
                "event_name": "page_view",
                "user_pseudo_id": "fixture-user-002",
                "event_params": [],
                "items": [],
                "traffic_source": {"source": "direct", "medium": "(none)"},
                "device": {"category": "mobile"},
                "geo": {"country": "Canada"},
                "ecommerce": {},
                "privacy_info": {"analytics_storage": "No"},
            },
        ]
    )


def test_ga4_contract_quarantines_invalid_timestamp(ga4_fixture: pd.DataFrame) -> None:
    ga4_fixture.loc[0, "event_timestamp"] = -1

    report = validate_ga4_events(ga4_fixture)

    assert report.valid_count == len(ga4_fixture) - 1
    assert report.quarantine.iloc[0]["reason"] == "event_timestamp_out_of_range"
    assert report.quarantine.iloc[0]["source_row_id"] == 0


def test_ga4_contract_normalizes_nested_fields_without_defaulting_missing_values(
    ga4_fixture: pd.DataFrame,
) -> None:
    ga4_fixture.at[1, "ecommerce"] = {"transaction_id": "T-002"}

    report = validate_ga4_events(ga4_fixture)

    first = report.valid.iloc[0]
    second = report.valid.iloc[1]
    assert first["event_params"]["ga_session_id"] == 1001
    assert first["items"][0]["quantity"] == 2
    assert first["traffic_source_source"] == "google"
    assert first["device_category"] == "desktop"
    assert first["geo_country"] == "United States"
    assert first["ecommerce_purchase_revenue"] == 39.0
    assert first["privacy_info_analytics_storage"] == "Yes"
    assert pd.isna(second["ecommerce_purchase_revenue"])


def test_ga4_contract_assigns_one_deterministic_primary_reason(
    ga4_fixture: pd.DataFrame,
) -> None:
    ga4_fixture.loc[0, "event_timestamp"] = 1580515200000000
    ga4_fixture.loc[0, "user_pseudo_id"] = ""
    ga4_fixture.loc[0, "items"] = [{"item_id": "sku-001", "quantity": 0}]

    report = validate_ga4_events(ga4_fixture)

    quarantined = report.quarantine.iloc[0]
    assert quarantined["reason"] == "event_outside_documented_coverage"
    assert quarantined["reasons"] == [
        "event_outside_documented_coverage",
        "user_pseudo_id_malformed",
        "item_quantity_invalid",
    ]


def test_ga4_contract_quarantines_negative_revenue_and_bad_item_quantity(
    ga4_fixture: pd.DataFrame,
) -> None:
    ga4_fixture.at[0, "ecommerce"] = {"purchase_revenue": -0.01}
    ga4_fixture.at[1, "items"] = [{"item_id": "sku-002", "quantity": -1}]

    report = validate_ga4_events(ga4_fixture)

    assert report.valid_count == 0
    assert report.quarantine_count == 2
    assert report.quarantine["reason"].tolist() == [
        "ecommerce_revenue_negative",
        "item_quantity_invalid",
    ]


def test_load_ga4_export_reads_nested_ndjson_and_preserves_source_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fixture.ndjson"
    rows = [
        {
            "event_timestamp": 1609459200000000,
            "event_name": "page_view",
            "user_pseudo_id": "fixture-user-001",
            "event_params": [{"key": "page_title", "value": {"string_value": "Home"}}],
        },
        {
            "event_timestamp": 1609545600000000,
            "event_name": "page_view",
            "user_pseudo_id": "fixture-user-002",
            "event_params": [],
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    frame = load_ga4_export(path)

    assert frame["source_row_id"].tolist() == [0, 1]
    assert frame.loc[0, "event_params"][0]["key"] == "page_title"
