"""Data-quality contracts for marketing measurement inputs."""

from .contracts import ValidationReport, validate_ga4_events

__all__ = ["ValidationReport", "validate_ga4_events"]
