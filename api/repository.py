"""Read-only access to reviewed, committed portfolio artifacts."""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Any, cast


class ArtifactRepository:
    """Loads only reviewed artifacts; it never queries a cloud data source."""

    _root = Path(__file__).resolve().parents[1]

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

    def _load(self, relative_path: str) -> Any:
        with (self._root / relative_path).open(encoding="utf-8") as artifact:
            return json.load(artifact)
