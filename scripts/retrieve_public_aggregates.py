"""Retrieve bounded, aggregate-only GA4 public sample artifacts with BigQuery CLI."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "christina-data-portfolio-2026"
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


def _run_bq(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bq", f"--project_id={PROJECT_ID}", *arguments],
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


def main() -> None:
    """Dry-run every query before retrieving its compact aggregate-only result."""
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(UTC).isoformat()
    metadata: dict[str, object] = {
        "project_id": PROJECT_ID,
        "maximum_bytes_billed": MAXIMUM_BYTES_BILLED,
        "retrieved_at_utc": retrieved_at,
        "queries": {},
    }
    for name in QUERY_NAMES:
        sql_path = SQL_DIRECTORY / f"{name}.sql"
        sql = sql_path.read_text(encoding="utf-8")
        dry_run = _run_bq(_query_arguments(sql, dry_run=True))
        job_id = f"marketing_measurement_{name}_{datetime.now(UTC):%Y%m%d%H%M%S%f}"
        result = _run_bq(_query_arguments(sql, dry_run=False, job_id=job_id))
        job = _run_bq(["show", "--format=json", "-j", job_id])
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
