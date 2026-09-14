"""Retrieve a bounded, identifier-free session sample for the portfolio model."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ID = "christina-data-portfolio-2026"
MAXIMUM_BYTES_BILLED = 4_000_000_000
ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "bigquery" / "conversion_model_sessions.sql"
OUTPUT_PATH = (
    ROOT
    / "data"
    / "observed"
    / "ga4_public_sample"
    / "conversion_model_sessions.json.gz"
)
METADATA_PATH = (
    ROOT / "data" / "observed" / "ga4_public_sample" / "retrieval_metadata.json"
)
QUERY_NAME = "conversion_model_sessions"


def _run_bq(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bq", f"--project_id={PROJECT_ID}", *arguments],
        check=True,
        text=True,
        capture_output=True,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_dry_run_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    query = payload.get("statistics", {}).get("query", {})
    return {
        "bytes_processed": query.get("totalBytesProcessed"),
        "bytes_billed": query.get("totalBytesBilled"),
        "referenced_tables": query.get("referencedTables"),
        "statement_type": query.get("statementType"),
    }


def _safe_job_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    query = payload.get("statistics", {}).get("query", {})
    reference = payload.get("jobReference", {})
    return {
        "job_id": reference.get("jobId"),
        "location": reference.get("location"),
        "bytes_processed": query.get("totalBytesProcessed"),
        "bytes_billed": query.get("totalBytesBilled"),
        "cache_hit": query.get("cacheHit"),
    }


def _query_arguments(
    sql: str, *, dry_run: bool, job_id: str | None = None
) -> list[str]:
    arguments = [
        "query",
        "--use_legacy_sql=false",
        f"--maximum_bytes_billed={MAXIMUM_BYTES_BILLED}",
        "--format=json",
        "--max_rows=100000",
    ]
    if dry_run:
        arguments.append("--dry_run")
    elif job_id:
        arguments.append(f"--job_id={job_id}")
    arguments.append(sql)
    return arguments


def main() -> None:
    """Dry-run before retrieval, then record separate SQL and result hashes."""

    sql = SQL_PATH.read_text(encoding="utf-8")
    dry_run = _run_bq(_query_arguments(sql, dry_run=True))
    job_id = f"marketing_measurement_{QUERY_NAME}_{datetime.now(UTC):%Y%m%d%H%M%S%f}"
    result = _run_bq(_query_arguments(sql, dry_run=False, job_id=job_id))
    job = _run_bq(["show", "--format=json", "-j", job_id])
    with gzip.open(OUTPUT_PATH, "wt", encoding="utf-8") as output_file:
        output_file.write(result.stdout)
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    queries = metadata.setdefault("queries", {})
    queries[QUERY_NAME] = {
        "sql_path": str(SQL_PATH.relative_to(ROOT)),
        "sql_sha256": _sha256(SQL_PATH),
        "dry_run": _safe_dry_run_metadata(json.loads(dry_run.stdout)),
        "job": _safe_job_metadata(json.loads(job.stdout)),
        "result_path": str(OUTPUT_PATH.relative_to(ROOT)),
        "result_sha256": _sha256(OUTPUT_PATH),
        "scope": (
            "Identifier-free 10% deterministic user-level sample at one row per "
            "measured session for educational conversion-model evaluation."
        ),
    }
    metadata["retrieved_at_utc"] = datetime.now(UTC).isoformat()
    METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
