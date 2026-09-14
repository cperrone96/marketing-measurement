"""Regression checks for public aggregate artifacts and their scope boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from marketing_measurement.analysis.attribution import attribution_credits

PROJECT_ROOT = Path(__file__).parents[2]
OBSERVED = PROJECT_ROOT / "data" / "observed" / "ga4_public_sample"


def test_paths_keep_complete_30_day_lookback_eligibility_in_aggregate_output() -> None:
    paths = pd.read_json(OBSERVED / "conversion_channel_paths.json")
    conversion_dates = pd.to_datetime(paths["conversion_date"])
    lookback_dates = pd.to_datetime(paths["lookback_start_date"])

    assert conversion_dates.min() >= pd.Timestamp("2020-12-01")
    assert (conversion_dates - lookback_dates).dt.days.eq(30).all()
    assert paths["eligible_30_day_lookback"].astype(str).eq("true").all()


def test_all_observed_channel_credits_reconcile_to_eligible_conversion_denominator() -> None:
    paths = pd.read_json(OBSERVED / "conversion_channel_paths.json")
    rows: list[dict[str, object]] = []
    for path_index, path in paths.iterrows():
        rows.extend(
            {
                "conversion_id": f"observed_path_{path_index}",
                "channel": channel,
                "touch_number": touch_number,
                "conversion_weight": int(path["converted_sessions"]),
            }
            for touch_number, channel in enumerate(
                str(path["channel_path"]).split(" > "), start=1
            )
        )
    path_frame = pd.DataFrame(rows)
    denominator = float(paths["converted_sessions"].sum())

    for model in ("first_touch", "last_touch", "linear", "time_decay"):
        credits = attribution_credits(path_frame, model)
        all_channel_credit = credits["credit"] * credits["conversion_weight"]
        assert all_channel_credit.groupby(credits["channel"]).sum().sum() == pytest.approx(
            denominator
        )


def test_observed_queries_use_session_event_channels_and_true_first_touch_cohorts() -> None:
    funnel_sql = (PROJECT_ROOT / "sql" / "bigquery" / "funnel_daily_by_channel.sql").read_text()
    paths_sql = (PROJECT_ROOT / "sql" / "bigquery" / "conversion_channel_paths.sql").read_text()
    cohort_sql = (PROJECT_ROOT / "sql" / "bigquery" / "cohort_retention.sql").read_text()

    for sql in (funnel_sql, paths_sql):
        assert "traffic_source.source" not in sql
        assert "event_source" in sql
        assert "event_medium" in sql
        assert "GROUP BY user_pseudo_id, ga_session_id" in sql
    assert "session_start_date >= DATE '2020-12-01'" in paths_sql
    assert "user_first_touch_timestamp" in cohort_sql
    assert "MIN(session_date)" not in cohort_sql


def test_retrieval_metadata_includes_availability_and_cap() -> None:
    metadata = json.loads((OBSERVED / "retrieval_metadata.json").read_text())

    assert metadata["maximum_bytes_billed"] == 4_000_000_000
    assert "event_parameter_availability" in metadata["queries"]
    assert all(
        int(query["dry_run"]["bytes_processed"]) <= metadata["maximum_bytes_billed"]
        for query in metadata["queries"].values()
    )
