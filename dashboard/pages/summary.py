"""Executive decision summary."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from api.schemas import KpisResponse, SourcesResponse
from dashboard.components import (
    chart_record,
    decision_header,
    error_state,
    evidence_strip,
    methodology,
)


def layout(kpis: KpisResponse, sources: SourcesResponse) -> html.Div:
    by_name = {item.name: item.values for item in kpis.items}
    funnel = by_name.get("funnel", {})
    stages = [
        ("Views", int(funnel.get("views", 0))),
        ("Engaged", int(funnel.get("engaged_sessions", 0))),
        ("Purchases", int(funnel.get("purchases", 0))),
    ]
    figure = go.Figure(
        go.Bar(
            x=[value for _, value in stages],
            y=[name for name, _ in stages],
            orientation="h",
            marker_color=["#1e4d45", "#347568", "#bb6c3f"],
            text=[f"{value:,}" for _, value in stages],
            textposition="auto",
            insidetextfont={"color": "#f5f0e6"},
            outsidetextfont={"color": "#152b31"},
        )
    )
    _style_figure(figure, "Sessions in the reviewed public sample")
    source_by_kind = {
        item.evidence.evidence_type: item.evidence for item in sources.items
    }
    strips = [evidence_strip(source_by_kind["public_observed"])]
    if "synthetic" in source_by_kind:
        strips.append(evidence_strip(source_by_kind["synthetic"]))
    rows = [{"stage": name, "sessions": value} for name, value in stages]
    return html.Div(
        className="page page--summary",
        children=[
            decision_header(
                "Measurement decision room",
                "Investigate the engagement-to-cart transition before expanding acquisition spend.",
                "Use the journey view to isolate where intent is lost; treat this as a descriptive diagnostic, not a causal claim.",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Span("Decision status", className="tally-label"),
                            html.Strong("INVESTIGATE", className="tally-status"),
                            dcc.Link(
                                "Open journey evidence",
                                href="/journeys",
                                className="primary-link",
                            ),
                        ],
                        className="decision-tally",
                    ),
                    chart_record(
                        "Observed journey tally",
                        "Views, engaged sessions, and purchases from the reviewed public GA4 sample.",
                        figure,
                        [("stage", "Journey stage"), ("sessions", "Sessions")],
                        rows,
                        chart_id="summary-funnel",
                    ),
                ],
                className="summary-lead",
            ),
            html.Section(
                [
                    html.H2("Evidence lanes"),
                    html.Div(strips, className="evidence-lanes"),
                ]
            ),
            html.P(
                "Attribution is descriptive, not causal", className="causal-warning"
            ),
            methodology(
                [
                    html.P(sources.boundary),
                    html.P("Public sample window: 2020-11-01 through 2021-01-31."),
                    html.P(
                        "Synthetic integration records demonstrate engineering and planning behavior only."
                    ),
                ]
            ),
        ],
    )


def error_layout(message: str) -> html.Div:
    return html.Div(
        [
            decision_header(
                "Measurement decision room",
                "Evidence is not loaded.",
                "Retry when the API is available.",
            ),
            error_state(message),
        ]
    )


def _style_figure(figure: go.Figure, x_title: str) -> None:
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f5f0e6",
        font={"color": "#152b31", "family": "Arial, sans-serif"},
        margin={"l": 90, "r": 80, "t": 16, "b": 54},
        height=290,
        xaxis_title=x_title,
        yaxis={"autorange": "reversed"},
        showlegend=False,
    )
    figure.update_xaxes(gridcolor="#c9c1b1", zeroline=False)
