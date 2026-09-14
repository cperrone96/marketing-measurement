from __future__ import annotations

import pandas as pd

from marketing_measurement.quality.contracts import ValidationReport


def test_validation_report_exposes_required_counts() -> None:
    report = ValidationReport(valid=pd.DataFrame([{"source_row_id": 2}]), quarantine=pd.DataFrame())

    assert report.valid_count == 1
    assert report.quarantine_count == 0
