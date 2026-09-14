"""Execute portfolio notebooks in an isolated copy without mutating evidence."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_NOTEBOOKS = (
    "notebooks/01_public_data_findings.ipynb",
    "notebooks/02_conversion_model.ipynb",
)
GENERATED_EVIDENCE = (
    "data/derived/ga4_public_sample/findings_summary.json",
)


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
        for relative_artifact in GENERATED_EVIDENCE:
            generated = workspace / relative_artifact
            reviewed = root / relative_artifact
            if generated.read_bytes() != reviewed.read_bytes():
                raise EvidenceIntegrityError(
                    f"notebook-generated evidence differs from reviewed artifact: "
                    f"{relative_artifact}"
                )

    verify_release_checksums(root, "after")


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
