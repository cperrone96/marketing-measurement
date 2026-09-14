"""Funnel and descriptive attribution diagnostics."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import html

from api.schemas import AttributionResponse, FunnelResponse, KpisResponse
from dashboard.components import (
    chart_record,
    decision_header,
    empty_state,
    evidence_strip,
    methodology,
)


def layout(
    funnel: FunnelResponse,
    attribution: AttributionResponse,
    kpis: KpisResponse | None = None,
) -> html.Div:
    stages = funnel.decision_summary.stages
    if stages.views == 0:
        return html.Div(
            [
                decision_header(
                    "Journey diagnostics",
                    "No journey can be evaluated.",
                    "Return to the full sample window.",
                ),
                empty_state("Reset the date range to load journey evidence."),
                methodology([html.P("Attribution is descriptive, not causal.")]),
                _empty_table(),
            ],
            className="page",
        )
    totals = {
        "Views": stages.views,
        "Engaged": stages.engaged_sessions,
        "Cart": stages.add_to_carts,
        "Checkout": stages.checkouts,
        "Purchase": stages.purchases,
    }
    funnel_rows = [
        {"stage": stage, "sessions": sessions} for stage, sessions in totals.items()
    ]
    funnel_figure = go.Figure(
        go.Funnel(
            y=list(totals),
            x=list(totals.values()),
            marker={"color": ["#1e4d45", "#347568", "#87794d", "#bb6c3f", "#8a3f33"]},
        )
    )
    _style(funnel_figure, 390)
    attribution_rows = [
        {
            "model": item.model.replace("_", " ").title(),
            "credit": item.conversion_credit_total,
            "leading_channel": next(iter(item.top_channel_credits), "Not available"),
            "leading_credit": next(iter(item.top_channel_credits.values()), 0),
        }
        for item in attribution.items
    ]
    analyses = {item.analysis: item for item in (kpis.analyses if kpis else [])}
    attribution_figure = go.Figure(
        go.Bar(
            x=[row["model"] for row in attribution_rows],
            y=[row["leading_credit"] for row in attribution_rows],
            marker_color="#5b4c91",
        )
    )
    _style(attribution_figure, 330)
    attribution_figure.update_layout(yaxis_title="Credit assigned to leading channel")
    return html.Div(
        className="page",
        children=[
            decision_header(
                "Journey diagnostics",
                "Fix measurement and the cart transition before treating channel differences as investment proof.",
                "Use attribution only to compare descriptive credit rules; it does not estimate incremental lift.",
            ),
            evidence_strip(funnel.evidence),
            html.P(
                "Attribution is descriptive, not causal", className="causal-warning"
            ),
            chart_record(
                "Journey progression",
                "API-computed session counts across the complete filtered window at each observed funnel stage.",
                funnel_figure,
                [("stage", "Journey stage"), ("sessions", "Sessions")],
                funnel_rows,
                chart_id="journey-funnel",
            ),
            chart_record(
                "Attribution model comparison",
                "Leading-channel conversion credit under four descriptive allocation rules.",
                attribution_figure,
                [
                    ("model", "Attribution model"),
                    ("credit", "Total conversion credit"),
                    ("leading_channel", "Leading channel"),
                    ("leading_credit", "Leading-channel credit"),
                ],
                attribution_rows,
                chart_id="journey-attribution",
            ),
            *[
                _analysis_record(
                    title,
                    analyses[name].decision,
                    [dict(row) for row in analyses[name].rows],
                    f"journey-{name}",
                )
                for name, title in (
                    ("product_revenue", "Product and revenue performance"),
                    ("high_value_journey", "High-value journeys"),
                )
                if name in analyses
            ],
            methodology(
                [
                    html.P(
                        "All four attribution models reconcile to the same eligible conversion total."
                    ),
                    html.P(
                        "Eligibility requires a complete 30-day lookback; allocation rules are descriptive, not causal."
                    ),
                ]
            ),
        ],
    )


def _analysis_record(
    title: str, decision: str, rows: list[dict[str, object]], chart_id: str
) -> html.Section:
    figure = go.Figure(
        go.Bar(
            x=[str(row["dimension"]) for row in rows],
            y=[float(row.get("revenue") or 0) for row in rows],
            marker_color="#bb6c3f",
        )
    )
    _style(figure, 360)
    figure.update_layout(yaxis_title="Observed revenue")
    columns = [(key, key.replace("_", " ").title()) for key in rows[0]] if rows else []
    return chart_record(title, decision, figure, columns, rows, chart_id=chart_id)


def _empty_table() -> html.Details:
    return html.Details(
        [
            html.Summary("View evidence table"),
            html.P("No rows are available for this selection."),
        ]
    )


def _style(figure: go.Figure, height: int) -> None:
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f5f0e6",
        font={"color": "#152b31", "family": "IBM Plex Mono, Menlo, monospace"},
        margin={"l": 64, "r": 30, "t": 18, "b": 60},
        height=height,
        showlegend=False,
    )
    figure.update_xaxes(gridcolor="#c9c1b1")
    figure.update_yaxes(gridcolor="#c9c1b1", zeroline=False)
