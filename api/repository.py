"""Read-only access to reviewed, committed portfolio artifacts."""

from __future__ import annotations

import hashlib
import json
from functools import cached_property
from pathlib import Path
from typing import Any, cast


class ArtifactRepository:
    """Loads only reviewed artifacts; it never queries a cloud data source."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parents[1]

    @cached_property
    def findings(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self._load("data/derived/ga4_public_sample/findings_summary.json"),
        )

    @cached_property
    def manifest(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._load("data/manifests/ga4_sample.json"))

    @cached_property
    def funnel(self) -> list[dict[str, str]]:
        return cast(
            list[dict[str, str]],
            self._load("data/observed/ga4_public_sample/funnel_daily_by_channel.json"),
        )

    @cached_property
    def cohorts(self) -> list[dict[str, str]]:
        return cast(
            list[dict[str, str]],
            self._load("data/observed/ga4_public_sample/cohort_retention.json"),
        )

    @cached_property
    def model_evaluation(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self._load("data/derived/ga4_public_sample/conversion_model_evaluation.json"),
        )

    @cached_property
    def portfolio_analyses(self) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            self._load(
                "data/observed/ga4_public_sample/portfolio_decision_aggregates.json"
            ),
        )

    def _load(self, relative_path: str) -> Any:
        with (self._root / relative_path).open(encoding="utf-8") as artifact:
            return json.load(artifact)

    def source_sha256(self, relative_path: str) -> str:
        """Return the committed generator artifact digest without exposing its path."""
        return hashlib.sha256((self._root / relative_path).read_bytes()).hexdigest()

    def composite_source_sha256(self, relative_paths: tuple[str, ...]) -> str:
        """Hash a canonical manifest of exact source paths and their content hashes."""
        manifest = [
            {"artifact": path, "sha256": self.source_sha256(path)}
            for path in sorted(relative_paths)
        ]
        canonical = json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
