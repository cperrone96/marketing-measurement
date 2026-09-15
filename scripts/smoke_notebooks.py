"""Execute portfolio notebooks in an isolated copy without mutating evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import cast

DEFAULT_NOTEBOOKS = (
    "notebooks/01_public_data_findings.ipynb",
    "notebooks/02_conversion_model.ipynb",
)
GENERATED_EVIDENCE = (
    "data/derived/ga4_public_sample/findings_summary.json",
    "data/derived/ga4_public_sample/conversion_model_evaluation.json",
)
MODEL_EVIDENCE = "data/derived/ga4_public_sample/conversion_model_evaluation.json"
NUMERIC_TOLERANCE = 1e-4


class EvidenceIntegrityError(RuntimeError):
    """Raised when tracked evidence differs from the reviewed release bytes."""


def verify_release_checksums(root: Path, phase: str) -> None:
    """Verify every release-manifest entry without changing the source tree."""
    manifest = root / "docs/release-checksums.sha256"
    if not manifest.is_file():
        raise EvidenceIntegrityError(f"release checksum manifest is missing: {manifest}")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative_path = line.split(maxsplit=1)
        artifact = root / relative_path.lstrip(" *")
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual != expected:
            raise EvidenceIntegrityError(
                f"checksum mismatch {phase} notebook execution: {artifact.relative_to(root)}"
            )


def run_notebook_smoke(root: Path, output_dir: Path) -> None:
    """Execute in a temporary worktree, compare output, and recheck source bytes."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    verify_release_checksums(root, "before")
    verify_committed_notebooks_are_clean(root)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="workspace-", dir=output_dir) as temporary:
        workspace = Path(temporary) / "project"
        shutil.copytree(
            root,
            workspace,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                ".artifacts",
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
                "__pycache__",
                "*.pyc",
            ),
        )
        prepare_generated_evidence(workspace)
        environment = os.environ.copy()
        environment["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{environment['PATH']}"
        for relative_notebook in DEFAULT_NOTEBOOKS:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "nbconvert",
                    "--to",
                    "notebook",
                    "--execute",
                    "--output-dir",
                    str(output_dir),
                    relative_notebook,
                ],
                cwd=workspace,
                env=environment,
                check=True,
            )
        verify_generated_evidence(workspace, root)
        verify_generated_notebooks(output_dir, root)

    verify_release_checksums(root, "after")


def normalize_notebook(notebook: dict[str, object]) -> dict[str, object]:
    """Return notebook structure without volatile execution state."""
    normalized = json.loads(json.dumps(notebook))
    cells = normalized.get("cells", [])
    if isinstance(cells, list):
        for cell in cells:
            if isinstance(cell, dict) and cell.get("cell_type") == "code":
                cell["execution_count"] = None
                cell["outputs"] = []
                cell_metadata = cell.get("metadata")
                if isinstance(cell_metadata, dict):
                    cell_metadata.pop("execution", None)
    metadata = normalized.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("widgets", None)
        language_info = metadata.get("language_info")
        if isinstance(language_info, dict):
            language_info.pop("version", None)
    return cast(dict[str, object], normalized)


def verify_committed_notebooks_are_clean(root: Path) -> None:
    """Reject committed execution output, which becomes stale evidence silently."""
    for relative_notebook in DEFAULT_NOTEBOOKS:
        notebook = json.loads((root / relative_notebook).read_text(encoding="utf-8"))
        code_cells = [
            cell for cell in notebook.get("cells", [])
            if isinstance(cell, dict) and cell.get("cell_type") == "code"
        ]
        if any(
            cell.get("outputs")
            or cell.get("execution_count") is not None
            or (
                isinstance(cell.get("metadata"), dict)
                and "execution" in cell["metadata"]
            )
            for cell in code_cells
        ):
            raise EvidenceIntegrityError(
                f"committed notebook contains stale execution output: {relative_notebook}"
            )


def verify_generated_notebooks(output_dir: Path, canonical_root: Path) -> None:
    """Require fresh executed notebooks with unchanged source and visible outputs."""
    for relative_notebook in DEFAULT_NOTEBOOKS:
        reviewed_path = canonical_root / relative_notebook
        generated_path = output_dir / Path(relative_notebook).name
        if not generated_path.is_file():
            raise EvidenceIntegrityError(
                f"fresh executed notebook is missing: {generated_path.name}"
            )
        reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
        generated = json.loads(generated_path.read_text(encoding="utf-8"))
        if normalize_notebook(generated) != normalize_notebook(reviewed):
            raise EvidenceIntegrityError(
                f"executed notebook source differs from reviewed source: {relative_notebook}"
            )
        code_cells = [
            cell for cell in generated.get("cells", [])
            if isinstance(cell, dict) and cell.get("cell_type") == "code"
        ]
        if not code_cells or any(cell.get("execution_count") is None for cell in code_cells):
            raise EvidenceIntegrityError(
                f"fresh notebook was not fully executed: {relative_notebook}"
            )


def prepare_generated_evidence(workspace: Path) -> None:
    """Remove copied generated outputs so notebooks must create fresh evidence."""
    for relative_artifact in GENERATED_EVIDENCE:
        generated = workspace / relative_artifact
        if generated.exists():
            generated.unlink()


def verify_generated_evidence(workspace: Path, canonical_root: Path) -> None:
    """Require fresh outputs and reject material evidence drift.

    Descriptive evidence remains byte-identical. Model metrics are compared
    structurally with a narrow tolerance because identical pinned scientific-Python
    versions can differ by a final floating-point digit across operating systems.
    """
    for relative_artifact in GENERATED_EVIDENCE:
        generated = workspace / relative_artifact
        reviewed = canonical_root / relative_artifact
        if not generated.is_file():
            raise EvidenceIntegrityError(
                f"notebook-generated evidence was not freshly created: {relative_artifact}"
            )
        if relative_artifact == MODEL_EVIDENCE:
            generated_json = json.loads(generated.read_text(encoding="utf-8"))
            reviewed_json = json.loads(reviewed.read_text(encoding="utf-8"))
            try:
                _assert_json_close(generated_json, reviewed_json, relative_artifact)
            except AssertionError as error:
                raise EvidenceIntegrityError(str(error)) from error
        elif generated.read_bytes() != reviewed.read_bytes():
            raise EvidenceIntegrityError(
                f"notebook-generated evidence differs from reviewed artifact: "
                f"{relative_artifact}"
            )


def _assert_json_close(generated: object, reviewed: object, path: str) -> None:
    """Compare JSON recursively while allowing only negligible numeric drift."""
    if isinstance(reviewed, bool) or reviewed is None or isinstance(reviewed, str):
        assert generated == reviewed, f"material evidence drift at {path}"
        return
    if isinstance(reviewed, (int, float)):
        assert isinstance(generated, (int, float)) and not isinstance(generated, bool), (
            f"evidence type drift at {path}"
        )
        assert abs(float(generated) - float(reviewed)) <= NUMERIC_TOLERANCE, (
            f"material numeric evidence drift at {path}: "
            f"generated={generated}, reviewed={reviewed}"
        )
        return
    if isinstance(reviewed, list):
        assert isinstance(generated, list) and len(generated) == len(reviewed), (
            f"evidence structure drift at {path}"
        )
        for index, (generated_item, reviewed_item) in enumerate(
            zip(generated, reviewed, strict=True)
        ):
            _assert_json_close(generated_item, reviewed_item, f"{path}[{index}]")
        return
    assert isinstance(reviewed, dict) and isinstance(generated, dict), (
        f"evidence structure drift at {path}"
    )
    assert generated.keys() == reviewed.keys(), f"evidence key drift at {path}"
    for key in reviewed:
        _assert_json_close(generated[key], reviewed[key], f"{path}.{key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        run_notebook_smoke(arguments.root, arguments.output_dir)
    except (EvidenceIntegrityError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
