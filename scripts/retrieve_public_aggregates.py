"""Retrieve bounded, aggregate-only GA4 public sample artifacts with BigQuery CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

MAXIMUM_BYTES_BILLED = 4_000_000_000
ROOT = Path(__file__).resolve().parents[1]
SQL_DIRECTORY = ROOT / "sql" / "bigquery"
OUTPUT_DIRECTORY = ROOT / "data" / "observed" / "ga4_public_sample"
QUERY_NAMES = (
    "event_parameter_availability",
    "funnel_daily_by_channel",
    "cohort_retention",
    "conversion_channel_paths",
)


def _run_bq(project_id: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bq", f"--project_id={project_id}", *arguments],
        check=True,
        text=True,
        capture_output=True,
    )


def _query_arguments(sql: str, dry_run: bool, job_id: str | None = None) -> list[str]:
    arguments = [
        "query",
        "--use_legacy_sql=false",
        f"--maximum_bytes_billed={MAXIMUM_BYTES_BILLED}",
        "--format=json",
        "--max_rows=10000",
    ]
    if dry_run:
        arguments.append("--dry_run")
    elif job_id is not None:
        arguments.append(f"--job_id={job_id}")
    arguments.append(sql)
    return arguments


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_dry_run_metadata(payload: dict[str, object]) -> dict[str, object]:
    statistics = payload.get("statistics", {})
    query = statistics.get("query", {}) if isinstance(statistics, dict) else {}
    return {
        "bytes_processed": query.get("totalBytesProcessed"),
        "bytes_billed": query.get("totalBytesBilled"),
        "referenced_tables": query.get("referencedTables"),
        "statement_type": query.get("statementType"),
    }


def _safe_job_metadata(payload: dict[str, object]) -> dict[str, object]:
    statistics = payload.get("statistics", {})
    query = statistics.get("query", {}) if isinstance(statistics, dict) else {}
    reference = payload.get("jobReference", {})
    return {
        "job_id": reference.get("jobId") if isinstance(reference, dict) else None,
        "location": reference.get("location") if isinstance(reference, dict) else None,
        "bytes_processed": query.get("totalBytesProcessed"),
        "bytes_billed": query.get("totalBytesBilled"),
        "cache_hit": query.get("cacheHit"),
    }


PORTFOLIO_QUERY = "portfolio_decision_aggregates"
PORTFOLIO_SECTION_NAMES = {"product": "product_revenue"}
PORTFOLIO_SECTION_ORDER = ("device", "landing_page", "product_revenue", "high_value_journey")
PORTFOLIO_INTEGER_FIELDS = frozenset(
    {"sessions", "engaged_sessions", "purchases", "product_views", "add_to_carts", "units"}
)
PORTFOLIO_FLOAT_FIELDS = frozenset({"revenue", "conversion_rate"})


def billing_cap(dry_run_bytes: int) -> int:
    """Cap a real job just above its dry-run size, never above the hard ceiling."""
    cap = dry_run_bytes + 50 * 1024 * 1024
    if cap > MAXIMUM_BYTES_BILLED:
        raise ValueError(f"query would scan {dry_run_bytes} bytes, above the ceiling")
    return cap


def curate_portfolio_rows(rows: list[dict[str, str | None]]) -> list[dict[str, object]]:
    """Keep every device row and the five highest-revenue rows of each other section.

    Ties in revenue (for example abandoned journeys at zero) go to the larger row.

    BigQuery's JSON output is all strings; values are typed and null fields dropped.
    """
    typed: list[dict[str, object]] = []
    for row in rows:
        record: dict[str, object] = {}
        for key, value in row.items():
            if value is None:
                continue
            if key in PORTFOLIO_INTEGER_FIELDS:
                record[key] = int(value)
            elif key in PORTFOLIO_FLOAT_FIELDS:
                record[key] = float(value)
            else:
                record[key] = value
        record["analysis"] = PORTFOLIO_SECTION_NAMES.get(
            str(record["analysis"]), record["analysis"]
        )
        typed.append(record)
    curated: list[dict[str, object]] = []
    for section in PORTFOLIO_SECTION_ORDER:
        members = sorted(
            (row for row in typed if row["analysis"] == section),
            key=lambda row: (
                -float(str(row["revenue"])),
                -int(str(row.get("sessions", row.get("product_views", 0)))),
                str(row["dimension"]),
            ),
        )
        curated.extend(members if section == "device" else members[:5])
    return curated


def retrieve_queries(project_id: str, names: list[str]) -> None:
    """Re-run named queries with tight billing caps, merging into existing metadata."""
    metadata_path = OUTPUT_DIRECTORY / "retrieval_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for name in names:
        sql_path = SQL_DIRECTORY / f"{name}.sql"
        sql = sql_path.read_text(encoding="utf-8")
        dry_run = _safe_dry_run_metadata(
            json.loads(_run_bq(project_id, _query_arguments(sql, dry_run=True)).stdout)
        )
        cap = billing_cap(int(str(dry_run["bytes_processed"])))
        job_id = f"marketing_measurement_{name}_{datetime.now(UTC):%Y%m%d%H%M%S%f}"
        arguments = _query_arguments(sql, dry_run=False, job_id=job_id)
        arguments = [
            f"--maximum_bytes_billed={cap}" if item.startswith("--maximum_bytes") else item
            for item in arguments
        ]
        result = _run_bq(project_id, arguments)
        job = _safe_job_metadata(
            json.loads(_run_bq(project_id, ["show", "--format=json", "-j", job_id]).stdout)
        )
        output_path = OUTPUT_DIRECTORY / f"{name}.json"
        if name == PORTFOLIO_QUERY:
            rows = curate_portfolio_rows(json.loads(result.stdout))
            output_path.write_text(
                json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            portfolio_path = OUTPUT_DIRECTORY / f"{name}_metadata.json"
            portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
            portfolio.update(
                {
                    "billing_project": "owner-supplied billing project (not recorded)",
                    "dry_run_bytes_processed": int(str(dry_run["bytes_processed"])),
                    "job_bytes_billed": int(str(job["bytes_billed"])),
                    "job_bytes_processed": int(str(job["bytes_processed"])),
                    "job_id": job["job_id"],
                    "maximum_bytes_billed": cap,
                    "query_sha256": _sha256(sql_path),
                    "result_sha256": _sha256(output_path),
                    "retrieved_at_utc": datetime.now(UTC).isoformat(),
                }
            )
            portfolio_path.write_text(
                json.dumps(portfolio, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            continue
        output_path.write_text(result.stdout, encoding="utf-8")
        metadata["queries"][name] = {
            "sql_path": str(sql_path.relative_to(ROOT)),
            "sql_sha256": _sha256(sql_path),
            "dry_run": dry_run,
            "job": job,
            "maximum_bytes_billed": cap,
            "retrieved_at_utc": datetime.now(UTC).isoformat(),
            "result_path": str(output_path.relative_to(ROOT)),
            "result_sha256": _sha256(output_path),
        }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    """Dry-run every query before retrieving its compact aggregate-only result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument(
        "--only",
        nargs="+",
        choices=(*QUERY_NAMES, PORTFOLIO_QUERY),
        help="re-run only these queries and merge into the existing metadata",
    )
    arguments = parser.parse_args()
    if arguments.only:
        retrieve_queries(arguments.project_id, arguments.only)
        return
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()
    metadata: dict[str, object] = {
        "project_id": arguments.project_id,
        "maximum_bytes_billed": MAXIMUM_BYTES_BILLED,
        "retrieved_at_utc": retrieved_at,
        "queries": {},
    }
    for name in QUERY_NAMES:
        sql_path = SQL_DIRECTORY / f"{name}.sql"
        sql = sql_path.read_text(encoding="utf-8")
        dry_run = _run_bq(arguments.project_id, _query_arguments(sql, dry_run=True))
        job_id = f"marketing_measurement_{name}_{datetime.now(UTC):%Y%m%d%H%M%S%f}"
        result = _run_bq(
            arguments.project_id, _query_arguments(sql, dry_run=False, job_id=job_id)
        )
        job = _run_bq(arguments.project_id, ["show", "--format=json", "-j", job_id])
        output_path = OUTPUT_DIRECTORY / f"{name}.json"
        output_path.write_text(result.stdout, encoding="utf-8")
        metadata["queries"][name] = {
            "sql_path": str(sql_path.relative_to(ROOT)),
            "sql_sha256": _sha256(sql_path),
            "dry_run": _safe_dry_run_metadata(json.loads(dry_run.stdout)),
            "job": _safe_job_metadata(json.loads(job.stdout)),
            "result_path": str(output_path.relative_to(ROOT)),
            "result_sha256": _sha256(output_path),
        }
    (OUTPUT_DIRECTORY / "retrieval_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
