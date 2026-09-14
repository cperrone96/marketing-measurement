"""Acquisition and cohort decision view."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import html

from api.schemas import CohortsResponse, FunnelResponse
from dashboard.components import (
    chart_record,
    decision_header,
    empty_state,
    evidence_strip,
    methodology,
)


def layout(funnel: FunnelResponse, cohorts: CohortsResponse) -> html.Div:
    channel_rows = [item.model_dump() for item in funnel.decision_summary.channels]
    cohort_rows = [item.model_dump() for item in cohorts.decision_summary.items]
    if not channel_rows and not cohort_rows:
        return html.Div(
            [
                decision_header(
                    "Acquisition signals",
                    "No decision can be called.",
                    "Reset the date range to the full public sample window.",
                ),
                empty_state("Reset the date range to 2020-11-01 through 2021-01-31."),
                methodology(
                    [html.P("This view uses public observed aggregates only.")]
                ),
                _empty_table(),
            ],
            className="page",
        )
    figure = go.Figure()
    for key, label, color in (
        ("views", "Views", "#9eb5af"),
        ("engaged_sessions", "Engaged", "#347568"),
        ("purchases", "Purchases", "#bb6c3f"),
    ):
        figure.add_bar(
            name=label,
            x=[row["channel"] for row in channel_rows],
            y=[row[key] for row in channel_rows],
            marker_color=color,
        )
    _style(figure, "Sessions by channel", barmode="group")

    cohort_figure = go.Figure(
        go.Scatter(
            x=[row["cohort_date"] for row in cohort_rows],
            y=[row["retention_rate"] for row in cohort_rows],
            mode="lines+markers",
            line={"color": "#5b4c91", "width": 3},
            marker={"size": 7},
        )
    )
    _style(cohort_figure, "Day-7 first-touch retention", percentage=True)
    return html.Div(
        className="page",
        children=[
            decision_header(
                "Acquisition signals",
                "Compare traffic sources on engagement quality before buying more reach.",
                "Use cohort retention as a supporting diagnostic; the public sample is old and ecommerce-specific.",
            ),
            evidence_strip(funnel.evidence),
            chart_record(
                "Channel quality tally",
                "The eight channels with the most engaged sessions, computed by the API from the complete filtered window; views and purchases provide context.",
                figure,
                [
                    ("channel", "Channel"),
                    ("views", "Views"),
                    ("engaged_sessions", "Engaged"),
                    ("purchases", "Purchases"),
                ],
                channel_rows,
                chart_id="acquisition-channels",
            ),
            chart_record(
                "Day-7 cohort return",
                "All first-touch cohorts observed seven days after acquisition where the filtered source window is complete.",
                cohort_figure,
                [
                    ("cohort_date", "Cohort date"),
                    ("days_since_acquisition", "Days since acquisition"),
                    ("cohort_users", "Cohort users"),
                    ("retained_users", "Retained users"),
                    ("retention_rate", "Retention rate"),
                ],
                cohort_rows,
                chart_id="acquisition-cohorts",
            ),
            methodology(
                [
                    html.P(
                        "Channels use the first paired event-scoped source and medium in each measured session."
                    ),
                    html.P(
                        "Retention uses true first-touch cohorts and complete day-7 follow-up only."
                    ),
                    html.P(
                        "The API computes channel totals and retention rates across the complete filtered window before paginating detail rows."
                    ),
                ]
            ),
        ],
    )


def _empty_table() -> html.Details:
    return html.Details(
        [
            html.Summary("View evidence table"),
            html.P("No rows are available for this selection."),
        ]
    )


def _style(
    figure: go.Figure,
    title: str,
    *,
    barmode: str | None = None,
    percentage: bool = False,
) -> None:
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f5f0e6",
        font={"color": "#152b31", "family": "IBM Plex Mono, Menlo, monospace"},
        margin={"l": 64, "r": 24, "t": 24, "b": 90},
        height=380,
        yaxis_title=title,
        barmode=barmode,
        legend={"orientation": "h"},
    )
    figure.update_xaxes(gridcolor="#c9c1b1", tickangle=-24)
    figure.update_yaxes(
        gridcolor="#c9c1b1", tickformat=".1%" if percentage else None, zeroline=False
    )
