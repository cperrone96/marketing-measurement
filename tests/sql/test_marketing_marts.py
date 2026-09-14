"""Cross-engine reconciliation tests for the GA4 analytical marts.

The input records are deterministic synthetic fixtures passed through the Task 2
normalization and validation contract.  They are not observed Google data.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import time
from collections.abc import Generator, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from marketing_measurement.ingestion.ga4 import load_ga4_export
from marketing_measurement.quality.contracts import validate_ga4_events

PROJECT_ROOT = Path(__file__).parents[2]
SQL_FILES = (
    PROJECT_ROOT / "sql" / "001_namespaces.sql",
    PROJECT_ROOT / "sql" / "staging" / "stg_ga4_events.sql",
    PROJECT_ROOT / "sql" / "marts" / "mart_sessions.sql",
    PROJECT_ROOT / "sql" / "marts" / "mart_funnel.sql",
    PROJECT_ROOT / "sql" / "marts" / "mart_cohorts.sql",
    PROJECT_ROOT / "sql" / "marts" / "mart_products.sql",
)
PG_BIN = Path("/opt/homebrew/opt/postgresql@17/bin")


class Database:
    """Small DB-API adapter with one query surface for both real engines."""

    def __init__(self, connection: Any, engine: str) -> None:
        self.connection = connection
        self.engine = engine

    def sql(self, query: str, parameters: Sequence[Any] | None = None) -> Any:
        if self.engine == "duckdb":
            return self.connection.execute(query, parameters or [])
        cursor = self.connection.cursor()
        cursor.execute(query, parameters)
        return cursor

    def executemany(self, query: str, rows: Sequence[Sequence[Any]]) -> None:
        if self.engine == "duckdb":
            self.connection.executemany(query, rows)
            return
        cursor = self.connection.cursor()
        cursor.executemany(query, rows)
        cursor.close()

    def close(self) -> None:
        self.connection.close()


@pytest.fixture
def db(request: pytest.FixtureRequest) -> Generator[Database, None, None]:
    """Seed validated events, then execute all project SQL when it exists.

    During the red TDD run the model files are absent, intentionally leaving the
    analytical relation missing.  Once the contract exists, each selected engine
    executes the same SQL files against its own real database.
    """
    engine = request.config.getoption("--engine")
    if engine == "duckdb":
        database, cleanup = _duckdb_database()
    else:
        database, cleanup = _postgresql_database()
    try:
        _create_raw_contract(database)
        _seed_validated_fixture(database)
        if all(path.exists() for path in SQL_FILES):
            for path in SQL_FILES[1:]:
                database.sql(path.read_text(encoding="utf-8"))
        yield database
    finally:
        database.close()
        cleanup()


def _duckdb_database() -> tuple[Database, Any]:
    import duckdb

    return Database(duckdb.connect(database=":memory:"), "duckdb"), lambda: None


def _postgresql_database() -> tuple[Database, Any]:
    import psycopg

    temporary_dir = Path(
        tempfile.mkdtemp(prefix="marketing-measurement-pg-", dir="/private/tmp")
    )
    cluster_dir = temporary_dir / "data"
    socket_dir = temporary_dir / "socket"
    socket_dir.mkdir()
    port = _free_local_port()
    server: subprocess.Popen[str] | None = None
    try:
        subprocess.run(
            [str(PG_BIN / "initdb"), "-D", str(cluster_dir), "-A", "trust", "-U", "postgres"],
            check=True,
            capture_output=True,
            text=True,
        )
        server = subprocess.Popen(
            [
                str(PG_BIN / "postgres"),
                "-D",
                str(cluster_dir),
                "-p",
                str(port),
                "-k",
                str(socket_dir),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        connection = _connect_postgresql(psycopg, socket_dir, port, server)
    except BaseException:
        if server is not None:
            _stop_postgresql(server)
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise

    def cleanup() -> None:
        _stop_postgresql(server)
        shutil.rmtree(temporary_dir, ignore_errors=True)

    return Database(connection, "postgresql"), cleanup


def _connect_postgresql(
    psycopg: Any, socket_dir: Path, port: int, server: subprocess.Popen[str]
) -> Any:
    for _ in range(50):
        if server.poll() is not None:
            stderr = server.stderr.read() if server.stderr is not None else ""
            raise RuntimeError(f"Temporary PostgreSQL server exited during startup: {stderr}")
        try:
            return psycopg.connect(
                dbname="postgres",
                user="postgres",
                host=str(socket_dir),
                port=port,
                autocommit=True,
                connect_timeout=1,
            )
        except psycopg.OperationalError:
            time.sleep(0.1)
    raise RuntimeError("Temporary PostgreSQL server did not become ready within five seconds")


def _stop_postgresql(server: subprocess.Popen[str]) -> None:
    if server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)
    if server.stderr is not None:
        server.stderr.close()


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_handle:
        socket_handle.bind(("127.0.0.1", 0))
        return int(socket_handle.getsockname()[1])


def _create_raw_contract(database: Database) -> None:
    database.sql("CREATE SCHEMA IF NOT EXISTS raw_public")
    database.sql("CREATE SCHEMA IF NOT EXISTS staging")
    database.sql("CREATE SCHEMA IF NOT EXISTS analytics")
    database.sql(
        """
        CREATE TABLE raw_public.ga4_events (
            source_row_id BIGINT NOT NULL,
            event_timestamp BIGINT NOT NULL,
            event_name VARCHAR NOT NULL,
            user_pseudo_id VARCHAR NOT NULL,
            ga_session_id BIGINT,
            page_location VARCHAR,
            page_title VARCHAR,
            traffic_source_source VARCHAR,
            traffic_source_medium VARCHAR,
            traffic_source_name VARCHAR,
            device_category VARCHAR,
            geo_country VARCHAR,
            privacy_info_analytics_storage VARCHAR,
            engagement_time_msec BIGINT,
            purchase_revenue DOUBLE PRECISION,
            transaction_id VARCHAR,
            item_index BIGINT,
            item_id VARCHAR,
            item_name VARCHAR,
            item_category VARCHAR,
            item_quantity DOUBLE PRECISION,
            item_revenue DOUBLE PRECISION
        )
        """
    )
    database.sql(
        """
        CREATE TABLE raw_public.ga4_events_quarantine (
            source_row_id BIGINT NOT NULL,
            reason VARCHAR NOT NULL
        )
        """
    )


def _seed_validated_fixture(database: Database) -> None:
    fixture_path = PROJECT_ROOT / "data" / "fixtures" / "ga4_schema_fixture.ndjson"
    source = load_ga4_export(fixture_path)
    additions = pd.DataFrame(
        [
            _event("page_view", 1609455600000000, "fixture-user-001", 1001, page_location="/"),
            _event("user_engagement", 1609457400000000, "fixture-user-001", 1001, engagement_time_msec=12000),
            _event("add_to_cart", 1609458300000000, "fixture-user-001", 1001, item_id="sku-001", item_quantity=1),
            _event("purchase", 1609459200000000, "fixture-user-001", 1001, purchase_revenue=39.0, item_id="sku-001", item_quantity=2, item_revenue=39.0),
            _event("purchase", 1609459200000000, "fixture-user-001", 1001, purchase_revenue=39.0, item_id="sku-001", item_quantity=2, item_revenue=39.0),
            _event("page_view", -1, "quarantined-user", 9999, page_location="/blocked"),
        ]
    )
    additions.insert(0, "source_row_id", range(len(source), len(source) + len(additions)))
    frame = pd.concat([source, additions], ignore_index=True, sort=False)
    report = validate_ga4_events(frame)
    assert report.valid_count == 7
    assert report.quarantine_count == 1

    event_rows = [_raw_row(row) for row in report.valid.to_dict(orient="records")]
    placeholders = "?" if database.engine == "duckdb" else "%s"
    database.executemany(
        f"INSERT INTO raw_public.ga4_events VALUES ({', '.join([placeholders] * 22)})",
        event_rows,
    )
    quarantine_rows = [
        (int(row["source_row_id"]), str(row["reason"]))
        for row in report.quarantine.to_dict(orient="records")
    ]
    database.executemany(
        f"INSERT INTO raw_public.ga4_events_quarantine VALUES ({placeholders}, {placeholders})",
        quarantine_rows,
    )


def _event(
    event_name: str,
    event_timestamp: int,
    user_pseudo_id: str,
    ga_session_id: int,
    **fields: Any,
) -> dict[str, Any]:
    parameters = [{"key": "ga_session_id", "value": {"int_value": str(ga_session_id)}}]
    if "page_location" in fields:
        parameters.append(
            {"key": "page_location", "value": {"string_value": fields["page_location"]}}
        )
    if "engagement_time_msec" in fields:
        parameters.append(
            {
                "key": "engagement_time_msec",
                "value": {"int_value": str(fields["engagement_time_msec"])},
            }
        )
    ecommerce: dict[str, Any] = {}
    if "purchase_revenue" in fields:
        ecommerce["purchase_revenue"] = fields["purchase_revenue"]
    if "transaction_id" in fields:
        ecommerce["transaction_id"] = fields["transaction_id"]
    item: dict[str, Any] = {}
    for key in ("item_id", "item_name", "item_category", "item_quantity", "item_revenue"):
        if key in fields:
            item[{"item_quantity": "quantity"}.get(key, key)] = fields[key]
    return {
        "event_timestamp": event_timestamp,
        "event_name": event_name,
        "user_pseudo_id": user_pseudo_id,
        "event_params": parameters,
        "items": [item] if item else [],
        "traffic_source": {"source": "google", "medium": "organic", "name": "spring"},
        "device": {"category": "desktop"},
        "geo": {"country": "United States"},
        "ecommerce": ecommerce,
        "privacy_info": {"analytics_storage": "Yes"},
    }


def _raw_row(row: dict[str, Any]) -> tuple[Any, ...]:
    params = row.get("event_params") or {}
    items = row.get("items") or []
    item = items[0] if items else {}
    values = (
        row["source_row_id"],
        row["event_timestamp"],
        row["event_name"],
        row["user_pseudo_id"],
        params.get("ga_session_id"),
        params.get("page_location"),
        params.get("page_title"),
        row.get("traffic_source_source"),
        row.get("traffic_source_medium"),
        row.get("traffic_source_name"),
        row.get("device_category"),
        row.get("geo_country"),
        row.get("privacy_info_analytics_storage"),
        params.get("engagement_time_msec"),
        row.get("ecommerce_purchase_revenue"),
        row.get("ecommerce_transaction_id"),
        0 if items else None,
        item.get("item_id"),
        item.get("item_name"),
        item.get("item_category"),
        item.get("quantity"),
        item.get("item_revenue"),
    )
    return tuple(_database_value(value) for value in values)


def _database_value(value: Any) -> Any:
    """Translate pandas' missing scalar sentinel back to a database null."""
    return None if not isinstance(value, (list, dict)) and pd.isna(value) else value


def test_funnel_is_monotonic(db: Database) -> None:
    row = db.sql("SELECT * FROM analytics.mart_funnel_total").fetchone()
    assert row[0] == 2
    assert row[0] >= row[1] >= row[2] >= row[3]


def test_session_revenue_reconciles_to_events(db: Database) -> None:
    event_total = db.sql("SELECT SUM(purchase_revenue) FROM staging.stg_ga4_events").fetchone()[0]
    mart_total = db.sql("SELECT SUM(revenue) FROM analytics.mart_sessions").fetchone()[0]
    assert event_total == 39.0
    assert mart_total == event_total


def test_quarantined_and_duplicate_rows_do_not_reach_marts(db: Database) -> None:
    assert db.sql("SELECT COUNT(*) FROM raw_public.ga4_events_quarantine").fetchone()[0] == 1
    assert db.sql("SELECT COUNT(*) FROM staging.stg_ga4_events").fetchone()[0] == 5
    assert db.sql("SELECT SUM(purchases) FROM analytics.mart_funnel_total").fetchone()[0] == 1


def test_marts_preserve_unmeasured_revenue_and_expose_rate_inputs(db: Database) -> None:
    session = db.sql(
        """
        SELECT revenue FROM analytics.mart_sessions
        WHERE user_pseudo_id = 'fixture-user-002'
        """
    ).fetchone()
    funnel = db.sql("SELECT * FROM analytics.mart_funnel_total").fetchone()
    assert session[0] is None
    assert funnel[4:10] == (1, 2, 1, 1, 1, 1)


def test_product_and_cohort_marts_reconcile_fixture_values(db: Database) -> None:
    product = db.sql(
        "SELECT units, revenue, purchases FROM analytics.mart_products WHERE item_id = 'sku-001'"
    ).fetchone()
    cohort = db.sql("SELECT SUM(cohort_users), SUM(retained_users) FROM analytics.mart_cohorts").fetchone()
    assert product == (3.0, 39.0, 1)
    assert cohort == (2, 2)
