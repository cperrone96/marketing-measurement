"""Synthetic consent, audience, and delivery quality diagnostics."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import html

from api.schemas import AudienceQualityResponse, IntegrationHealthResponse
from dashboard.components import (
    chart_record,
    decision_header,
    empty_state,
    evidence_strip,
    methodology,
)


def layout(
    audience: AudienceQualityResponse, health: IntegrationHealthResponse
) -> html.Div:
    rows = [
        {
            "metric": item.metric.replace("_", " ").title(),
            "numerator": item.numerator,
            "denominator": item.denominator,
            "rate": item.rate,
        }
        for item in [*audience.items, *health.items]
    ]
    if not rows:
        return html.Div(
            [
                decision_header(
                    "Integration health",
                    "No synthetic run is available.",
                    "Retry the deterministic demonstration.",
                ),
                empty_state("Retry to regenerate the deterministic synthetic run."),
                methodology([html.P("Synthetic demonstration only.")]),
                _empty_table(),
            ],
            className="page",
        )
    figure = go.Figure(
        go.Bar(
            x=[row["rate"] or 0 for row in rows],
            y=[row["metric"] for row in rows],
            orientation="h",
            marker_color="#5b4c91",
            text=[f"{(row['rate'] or 0):.1%}" for row in rows],
            textposition="outside",
        )
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f5f0e6",
        font={"color": "#152b31", "family": "Arial, sans-serif"},
        margin={"l": 210, "r": 70, "t": 18, "b": 54},
        height=390,
        xaxis={"range": [0, 1.05], "tickformat": ".0%", "gridcolor": "#c9c1b1"},
        yaxis={"autorange": "reversed"},
        showlegend=False,
    )
    return html.Div(
        className="page",
        children=[
            decision_header(
                "Integration health",
                "Protect consent eligibility first, then investigate match and delivery losses in sequence.",
                "Use these records to review engineering controls—not to infer real platform performance.",
            ),
            evidence_strip(health.evidence),
            chart_record(
                "Synthetic delivery chain",
                "Rates from deterministic consent, partner-match, freshness, and delivery checks.",
                figure,
                [
                    ("metric", "Quality metric"),
                    ("numerator", "Numerator"),
                    ("denominator", "Denominator"),
                    ("rate", "Rate"),
                ],
                rows,
                chart_id="integration-rates",
            ),
            methodology(
                [
                    html.P(
                        "Synthetic planning demonstration; no live ad platform, customer identity, or campaign record is represented."
                    ),
                    html.P(
                        "Rates are computed from a fixed seed so results are reproducible and testable."
                    ),
                ]
            ),
        ],
    )


def _empty_table() -> html.Details:
    return html.Details(
        [
            html.Summary("View evidence table"),
            html.P("No rows are available for this run."),
        ]
    )
