"""Acquisition and cohort decision view."""

from __future__ import annotations

from collections import defaultdict

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
    if not funnel.items and not cohorts.items:
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
    channel_totals: dict[str, dict[str, int | str]] = defaultdict(
        lambda: {"channel": "", "views": 0, "engaged": 0, "purchases": 0}
    )
    for item in funnel.items:
        key = f"{item.channel_source} / {item.channel_medium}"
        channel_totals[key]["channel"] = key
        channel_totals[key]["views"] = int(channel_totals[key]["views"]) + item.views
        channel_totals[key]["engaged"] = (
            int(channel_totals[key]["engaged"]) + item.engaged_sessions
        )
        channel_totals[key]["purchases"] = (
            int(channel_totals[key]["purchases"]) + item.purchases
        )
    rows = sorted(
        channel_totals.values(), key=lambda row: int(row["engaged"]), reverse=True
    )[:8]
    figure = go.Figure()
    for key, label, color in (
        ("views", "Views", "#9eb5af"),
        ("engaged", "Engaged", "#347568"),
        ("purchases", "Purchases", "#bb6c3f"),
    ):
        figure.add_bar(
            name=label,
            x=[row["channel"] for row in rows],
            y=[row[key] for row in rows],
            marker_color=color,
        )
    _style(figure, "Sessions by channel", barmode="group")

    cohort_rows = [
        {
            "cohort_date": item.cohort_date,
            "days": item.days_since_acquisition,
            "cohort_users": item.cohort_users,
            "retained_users": item.retained_users,
            "retention": item.retained_users / item.cohort_users
            if item.cohort_users
            else None,
        }
        for item in cohorts.items
        if item.days_since_acquisition in {0, 7}
    ][:20]
    cohort_figure = go.Figure(
        go.Scatter(
            x=[row["cohort_date"] for row in cohort_rows if row["days"] == 7],
            y=[row["retention"] for row in cohort_rows if row["days"] == 7],
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
                "The eight channels with the most engaged sessions, with views and purchases shown for context.",
                figure,
                [
                    ("channel", "Channel"),
                    ("views", "Views"),
                    ("engaged", "Engaged"),
                    ("purchases", "Purchases"),
                ],
                rows,
                chart_id="acquisition-channels",
            ),
            chart_record(
                "Day-7 cohort return",
                "First-touch cohorts observed seven days after acquisition where the source window is complete.",
                cohort_figure,
                [
                    ("cohort_date", "Cohort date"),
                    ("days", "Days since acquisition"),
                    ("cohort_users", "Cohort users"),
                    ("retained_users", "Retained users"),
                    ("retention", "Retention rate"),
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
        font={"color": "#152b31", "family": "Arial, sans-serif"},
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
