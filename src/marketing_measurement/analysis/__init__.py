"""Offline descriptive analysis helpers for compact public-data aggregates."""

from .attribution import attribution_credits
from .cohorts import add_retention_rate
from .funnel import funnel_rates

__all__ = ["add_retention_rate", "attribution_credits", "funnel_rates"]
