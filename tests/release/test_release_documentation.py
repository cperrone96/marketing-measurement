"""Release-documentation contracts for a traceable, offline portfolio build."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
REQUIRED_DOCS = (
    "README.md",
    "docs/lineage.md",
    "docs/metric-dictionary.md",
    "docs/uat.md",
    "docs/risk-register.md",
    "docs/release-notes.md",
)


def test_release_documents_exist_and_keep_evidence_boundaries_visible() -> None:
    for relative_path in REQUIRED_DOCS:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "public observed" in text.lower(), relative_path
        assert "synthetic" in text.lower(), relative_path


def test_readme_headline_claims_match_reviewed_artifact() -> None:
    findings = json.loads(
        (ROOT / "data/derived/ga4_public_sample/findings_summary.json").read_text()
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    expected_fragments = (
        (
            f"{findings['funnel']['engaged_sessions']:,} of "
            f"{findings['funnel']['views']:,}"
        ),
        (
            f"{findings['day_7_retention']['retained_users']:,} of "
            f"{findings['day_7_retention']['cohort_users']:,}"
        ),
        f"{findings['attribution']['eligible_converted_sessions']:,}",
        findings["source"]["coverage_start"],
        findings["source"]["coverage_end"],
        "descriptive attribution; not causal",
    )
    for fragment in expected_fragments:
        assert fragment in readme


def test_release_checksums_match_committed_evidence() -> None:
    checksum_path = ROOT / "docs/release-checksums.sha256"
    rows = [line.split(maxsplit=1) for line in checksum_path.read_text().splitlines()]
    assert rows
    for expected, relative_path in rows:
        artifact = ROOT / relative_path
        assert artifact.is_file(), relative_path
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == expected


def test_ci_runs_offline_quality_gates_and_notebook_smoke() -> None:
    workflow_path = ROOT / ".github/workflows/ci.yml"
    commands = workflow_path.read_text(encoding="utf-8")

    for command in (
        "ruff check .",
        "mypy src api",
        "pytest -q",
        "make notebook-smoke",
        "make verify-checksums",
    ):
        assert command in commands
    assert "gcloud" not in commands
    assert "bigquery" not in commands.lower()
