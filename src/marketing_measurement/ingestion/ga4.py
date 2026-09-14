"""Load JSON and NDJSON exports shaped like nested GA4 event rows.

This module deliberately accepts exports only. It does not query BigQuery or require
Google credentials, keeping public-source retrieval separate from local processing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_ga4_export(path: Path) -> pd.DataFrame:
    """Load a JSON array, a ``{"rows": [...]}`` object, or line-delimited JSON.

    Nested objects and arrays remain nested so the validation boundary can normalize
    them consistently. ``source_row_id`` is assigned from the export row order and
    is retained by downstream quarantine records.
    """
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return pd.DataFrame({"source_row_id": pd.Series(dtype="int64")})

    try:
        decoded = json.loads(content)
        rows = _rows_from_json_document(decoded, path)
    except json.JSONDecodeError:
        rows = _rows_from_ndjson(content, path)

    frame = pd.DataFrame(rows)
    if "source_row_id" in frame.columns:
        raise ValueError("GA4 export reserves 'source_row_id' for loader row identity")
    frame.insert(0, "source_row_id", range(len(frame)))
    return frame


def _rows_from_json_document(decoded: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(decoded, list):
        rows = decoded
    elif isinstance(decoded, dict) and isinstance(decoded.get("rows"), list):
        rows = decoded["rows"]
    else:
        raise TypeError(f"{path} must contain a JSON array or an object with a rows array")
    return _validate_row_objects(rows, path)


def _rows_from_ndjson(content: str, path: Path) -> list[dict[str, Any]]:
    rows: list[Any] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on line {line_number} in {path}") from error
    return _validate_row_objects(rows, path)


def _validate_row_objects(rows: list[Any], path: Path) -> list[dict[str, Any]]:
    invalid_row = next((index for index, row in enumerate(rows) if not isinstance(row, dict)), None)
    if invalid_row is not None:
        raise ValueError(f"GA4 export row {invalid_row} in {path} is not a JSON object")
    return [dict(row) for row in rows]
