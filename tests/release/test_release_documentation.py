"""Release-documentation contracts for a traceable, offline portfolio build."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_every_readme_finding_matches_authoritative_evidence_and_is_traceable() -> None:
    findings = json.loads(
        (ROOT / "data/derived/ga4_public_sample/findings_summary.json").read_text()
    )
    model_card = (ROOT / "docs/models/conversion-model-card.md").read_text()
    readme = (ROOT / "README.md").read_text()
    sections = {
        number: re.search(
            rf"### {number}\. .*?(?=\n### |\n## )", readme, flags=re.DOTALL
        ).group(0)
        for number in range(1, 5)
    }

    funnel = findings["funnel"]
    funnel_fragments = (
        f"{funnel['engaged_sessions']:,} of {funnel['views']:,}",
        f"{funnel['engagement_rate']:.2%}",
        f"{funnel['add_to_carts']:,}",
        f"{funnel['add_to_cart_rate']:.2%}",
        f"{funnel['checkouts']:,}",
        f"{funnel['checkout_rate']:.2%}",
        f"{funnel['purchases']:,}",
        f"{funnel['purchase_rate']:.2%}",
    )
    retention = findings["day_7_retention"]
    retention_fragments = (
        f"{retention['eligible_cohorts']:,}",
        f"{retention['retained_users']:,} of {retention['cohort_users']:,}",
        f"{retention['rate']:.2%}",
    )
    attribution = findings["attribution"]
    attribution_fragments = (
        f"{attribution['eligible_converted_sessions']:,}",
        "2020-12-01 through 2021-01-31",
        f"{attribution['all_channel_credits']['first_touch']['google / organic']:,.0f}",
        f"{attribution['all_channel_credits']['last_touch']['google / organic']:,.0f}",
        attribution["interpretation"],
    )
    for section, fragments in zip(
        (sections[1], sections[2], sections[3]),
        (funnel_fragments, retention_fragments, attribution_fragments),
        strict=True,
    ):
        assert "**Evidence:** Public observed" in section
        assert "**Decision:**" in section
        assert "**Limitations:**" in section
        assert "**Trace:**" in section
        for fragment in fragments:
            assert fragment in section
    _assert_standard_finding_fields(sections[4])
    _assert_model_claim_matches(sections[4], model_card)

    required_trace_targets = {
        1: ("sql/bigquery/funnel_daily_by_channel.sql", "notebooks/01_public_data_findings.ipynb"),
        2: ("sql/bigquery/cohort_retention.sql", "notebooks/01_public_data_findings.ipynb"),
        3: ("sql/bigquery/conversion_channel_paths.sql", "src/marketing_measurement/analysis/attribution.py"),
        4: ("sql/bigquery/conversion_model_sessions.sql", "docs/models/conversion-model-card.md"),
    }
    for number, targets in required_trace_targets.items():
        for target in targets:
            assert f"]({target})" in sections[number]
            assert (ROOT / target).is_file()


def test_false_readme_model_pr_auc_is_rejected() -> None:
    readme = (ROOT / "README.md").read_text()
    model_card = (ROOT / "docs/models/conversion-model-card.md").read_text()
    model_section = re.search(
        r"### 4\. .*?(?=\n### |\n## )", readme, flags=re.DOTALL
    ).group(0)
    falsified = model_section.replace("0.041429 PR-AUC", "0.999999 PR-AUC")

    with pytest.raises(AssertionError):
        _assert_model_claim_matches(falsified, model_card)


def test_notebook_smoke_rejects_tampered_tracked_evidence_before_execution(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_text('{"value": "reviewed"}\n')
    expected = hashlib.sha256(artifact.read_bytes()).hexdigest()
    checksum_dir = tmp_path / "docs"
    checksum_dir.mkdir()
    (checksum_dir / "release-checksums.sha256").write_text(
        f"{expected}  evidence.json\n"
    )
    artifact.write_text('{"value": "tampered"}\n')

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/smoke_notebooks.py"),
            "--root",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "checksum mismatch before notebook execution" in result.stderr.lower()
    assert not (tmp_path / "outputs").exists()


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


def _model_card_value(model_card: str, row_label: str, column: str) -> str:
    header = next(line for line in model_card.splitlines() if "| ROC-AUC | PR-AUC |" in line)
    columns = [value.strip() for value in header.strip("|").split("|")]
    row = next(line for line in model_card.splitlines() if f"| {row_label} |" in line)
    values = [value.strip() for value in row.strip("|").split("|")]
    return values[columns.index(column)]


def _assert_standard_finding_fields(section: str) -> None:
    assert "**Evidence:** Public observed" in section
    assert "**Decision:**" in section
    assert "**Limitations:**" in section
    assert "**Trace:**" in section


def _assert_model_claim_matches(section: str, model_card: str) -> None:
    expected_fragments = (
        _model_card_value(model_card, "Logistic regression, held out", "PR-AUC"),
        _model_card_value(model_card, "No-skill prevalence, held out", "PR-AUC"),
        "7,245",
        "0.035589",
        "317",
        "6.94%",
        "21.78%",
        "101",
    )
    for fragment in expected_fragments:
        assert fragment in section
