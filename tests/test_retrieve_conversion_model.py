"""Regression tests for deterministic conversion-model artifact serialization."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from retrieve_public_conversion_model import _write_deterministic_gzip


def test_deterministic_gzip_has_identical_bytes_for_identical_rows(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.json.gz"
    second = tmp_path / "second.json.gz"
    logical_rows = '[{"a":"first","b":1},{"a":"second","b":2}]\n'

    _write_deterministic_gzip(first, logical_rows)
    _write_deterministic_gzip(second, logical_rows)

    assert first.read_bytes() == second.read_bytes()
    assert (
        hashlib.sha256(first.read_bytes()).hexdigest()
        == hashlib.sha256(second.read_bytes()).hexdigest()
    )
