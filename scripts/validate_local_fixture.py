"""Run the public ingestion contract over the redistributable schema fixture."""

from __future__ import annotations

from pathlib import Path

from marketing_measurement.ingestion.ga4 import load_ga4_export
from marketing_measurement.quality.contracts import validate_ga4_events


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = validate_ga4_events(
        load_ga4_export(root / "data/fixtures/ga4_schema_fixture.ndjson")
    )
    if report.quarantine_count:
        raise RuntimeError("redistributable fixture failed the ingestion contract")
    print(f"validated {report.valid_count} local fixture rows; no cloud access")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
