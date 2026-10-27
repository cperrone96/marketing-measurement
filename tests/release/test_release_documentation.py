"""Release-documentation contracts for a traceable, offline portfolio build."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.smoke_notebooks import (
    EvidenceIntegrityError,
    prepare_generated_evidence,
    verify_generated_evidence,
)

ROOT = Path(__file__).parents[2]
REQUIRED_DOCS = (
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
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "public" in readme
    assert "synthetic" in readme


def test_readme_key_results_match_generated_evidence() -> None:
    section = _readme_key_results()
    for fragment in _expected_key_result_fragments():
        assert fragment in section, fragment


def test_readme_key_results_reject_a_falsified_number() -> None:
    fragment = _pct(_model_evidence()["metrics"]["capacity_operating_point"]["precision"])
    falsified = _readme_key_results().replace(fragment, "99.99%")

    missing = [item for item in _expected_key_result_fragments() if item not in falsified]
    assert missing and all(fragment in item for item in missing)


def test_readme_figure_is_committed_and_referenced() -> None:
    figure = "docs/figures/attribution_by_channel_group.png"
    assert (ROOT / figure).is_file()
    assert f"]({figure})" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_model_card_matches_model_evidence() -> None:
    card = (ROOT / "docs/models/conversion-model-card.md").read_text(encoding="utf-8")
    evidence = _model_evidence()
    metrics = evidence["metrics"]
    capacity = metrics["capacity_operating_point"]
    intervals = metrics["selected_model_held_out_ci95"]
    for value in (
        metrics[f"{evidence['selected_model']}_held_out"]["pr_auc"],
        metrics["logistic_regression_held_out"]["pr_auc"],
        metrics["calibration"]["observed_to_expected_ratio"],
        metrics["no_skill_held_out"]["pr_auc"],
        metrics["returning_visitor_rule_held_out"]["pr_auc"],
        intervals["pr_auc_lower"],
        intervals["pr_auc_upper"],
        metrics["pr_auc_gain_over_returning_rule"]["estimate"],
        capacity["threshold"],
        capacity["precision"],
        capacity["recall"],
    ):
        assert f"{value:.6f}" in card, value
    assert f"{capacity['flagged_sessions']:,} of {capacity['held_out_sessions']:,}" in card
    assert f"{metrics['feature_coverage']['session_source_unattributed_share']:.2%}" in card
    assert f"{metrics['feature_coverage']['sessions']:,} sessions" in card


def test_notebook_smoke_requires_freshly_created_generated_evidence(
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    for root in (canonical, workspace):
        generated = root / "data/derived/ga4_public_sample/findings_summary.json"
        generated.parent.mkdir(parents=True)
        generated.write_text('{"status": "reviewed"}\n')

    prepare_generated_evidence(workspace)
    with pytest.raises(EvidenceIntegrityError, match="was not freshly created"):
        verify_generated_evidence(workspace, canonical)


def test_notebook_smoke_allows_only_negligible_cross_platform_model_drift(
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "canonical"
    workspace = tmp_path / "workspace"
    relative = Path(
        "data/derived/ga4_public_sample/conversion_model_evaluation.json"
    )
    for root, metric in ((canonical, 0.123456), (workspace, 0.123461)):
        artifact = root / relative
        artifact.parent.mkdir(parents=True)
        artifact.write_text(json.dumps({"metric": metric}) + "\n")
    for root in (canonical, workspace):
        summary = root / "data/derived/ga4_public_sample/findings_summary.json"
        summary.write_text('{"status": "reviewed"}\n')

    verify_generated_evidence(workspace, canonical)

    (workspace / relative).write_text(json.dumps({"metric": 0.1335}) + "\n")
    with pytest.raises(EvidenceIntegrityError, match="material numeric evidence drift"):
        verify_generated_evidence(workspace, canonical)


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


def test_notebook_smoke_compares_fresh_executed_notebooks_to_reviewed_outputs() -> None:
    smoke = (ROOT / "scripts/smoke_notebooks.py").read_text(encoding="utf-8")
    assert "verify_generated_notebooks" in smoke
    assert "normalize_notebook" in smoke


def test_postgres_port_is_localhost_only_and_not_trust_authenticated() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"127.0.0.1:5432:5432"' in compose
    assert "POSTGRES_HOST_AUTH_METHOD: trust" not in compose


def test_runtime_has_real_ingest_command_and_configurable_billing_project() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    retrieval = (ROOT / "scripts/retrieve_public_aggregates.py").read_text(encoding="utf-8")
    assert "ingest:" in makefile
    assert "--project-id" in retrieval


def _findings() -> dict[str, Any]:
    path = ROOT / "data/derived/ga4_public_sample/findings_summary.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _model_evidence() -> dict[str, Any]:
    path = ROOT / "data/derived/ga4_public_sample/conversion_model_evaluation.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _readme_key_results() -> str:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"## Key results\n.*?(?=\n## )", readme, flags=re.DOTALL)
    assert match is not None
    return match.group(0)


def _pct(value: float) -> str:
    return f"{value:.2%}"


def _expected_key_result_fragments() -> list[str]:
    """Every README headline number, formatted from the generated evidence."""
    findings = _findings()
    funnel = findings["funnel"]
    coverage = findings["funnel_coverage"]
    retention = findings["day_7_retention"]
    attribution = findings["attribution"]
    groups = attribution["channel_group_credits"]
    clean = attribution["channel_group_credits_excluding_self_referrals"]
    self_referral = attribution["self_referral"]
    evidence = _model_evidence()
    metrics = evidence["metrics"]
    selected = metrics[f"{evidence['selected_model']}_held_out"]
    capacity = metrics["capacity_operating_point"]
    intervals = metrics["selected_model_held_out_ci95"]
    gain = metrics["pr_auc_gain_over_returning_rule"]
    rule = metrics["returning_visitor_rule_held_out"]
    return [
        findings["source"]["coverage_start"],
        findings["source"]["coverage_end"],
        _pct(funnel["add_to_cart_rate"]),
        f"{funnel['add_to_carts']:,} of {funnel['engaged_sessions']:,}",
        _pct(funnel["engagement_rate"]),
        _pct(funnel["checkout_rate"]),
        _pct(funnel["purchase_rate"]),
        f"{funnel['view_to_purchase_rate']:.2%} of {funnel['views']:,}",
        (f"{coverage['strict_funnel_purchases']:,} of at least "
        f"{coverage['observed_purchase_sessions_lower_bound']:,}"),
        _pct(coverage["strict_funnel_share"]),
        f"{coverage['purchases_without_same_session_cart']:,} purchase sessions",
        _pct(retention["rate"]),
        f"{retention['retained_users']:,} of {retention['cohort_users']:,}",
        f"{retention['eligible_cohorts']} first-touch cohorts",
        (f"{self_referral['converted_sessions_with_self_referral_touch']:,} of "
        f"{attribution['eligible_converted_sessions']:,} converted sessions"),
        _pct(self_referral["share_of_converted_sessions"]),
        f"{self_referral['last_touch_credit_as_observed']:,.0f} last-touch credits",
        (f"{groups['first_touch']['Organic Search']:,.0f} vs "
        f"{groups['last_touch']['Organic Search']:,.0f} as observed"),
        (f"{clean['first_touch']['Organic Search']:,.0f} vs "
        f"{clean['last_touch']['Organic Search']:,.0f} with self-referrals removed"),
        f"ROC-AUC {selected['roc_auc']:.3f}",
        f"(ROC-AUC {rule['roc_auc']:.3f})",
        (f"PR-AUC {selected['pr_auc']:.4f} "
        f"(95% CI {intervals['pr_auc_lower']:.4f} to {intervals['pr_auc_upper']:.4f})"),
        f"No-skill {metrics['no_skill_held_out']['pr_auc']:.4f}",
        f"returning-visitor rule {metrics['returning_visitor_rule_held_out']['pr_auc']:.4f}",
        (f"gain over the rule {gain['estimate']:.4f} "
        f"(95% CI {gain['ci95_lower']:.4f} to {gain['ci95_upper']:.4f})"),
        (f"Precision {_pct(capacity['precision'])} "
        f"(95% CI {_pct(capacity['precision_ci95_lower'])} to "
        f"{_pct(capacity['precision_ci95_upper'])})"),
        f"{capacity['lift_over_prevalence']:.2f}x the base rate",
        f"Flags {capacity['flagged_sessions']:,} of {capacity['held_out_sessions']:,}",
        f"({_pct(capacity['flagged_share'])})",
        (f"finds {_pct(capacity['recall'])} of the "
        f"{capacity['held_out_conversions']:,} held-out conversions"),
    ]
