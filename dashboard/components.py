"""Reusable accessible components for evidence-led decision pages."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from dash import dcc, html
from plotly.graph_objects import Figure

from api.schemas import Evidence


def format_number(value: float | str | None) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, float) and 0 <= value <= 1:
        return f"{value:.1%}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return value


def evidence_label(evidence: Evidence) -> str:
    return (
        "Public GA4 evidence"
        if evidence.evidence_type == "public_observed"
        else "Synthetic integration demonstration"
    )


def evidence_strip(evidence: Evidence) -> html.Section:
    kind = "observed" if evidence.evidence_type == "public_observed" else "synthetic"
    return html.Section(
        className=f"evidence-strip evidence-strip--{kind}",
        **{"aria-label": f"{evidence_label(evidence)} provenance"},
        children=[
            html.Div(evidence_label(evidence), className="evidence-strip__label"),
            html.Div(
                evidence.source_date_or_window, className="evidence-strip__window"
            ),
            html.Details(
                [
                    html.Summary("Source, provenance, and limitations"),
                    html.P(f"Artifact: {evidence.provenance.artifact}"),
                    html.P(f"SHA-256: {evidence.provenance.sha256}", className="hash"),
                    html.Ul([html.Li(item) for item in evidence.limitations]),
                ]
            ),
        ],
    )


def decision_header(title: str, decision: str, action: str) -> html.Header:
    return html.Header(
        className="decision-header",
        children=[
            html.H1(title),
            html.Div(
                [
                    html.P(decision, className="decision-call"),
                    html.P(action, className="decision-action"),
                ],
                className="decision-copy",
            ),
        ],
    )


def data_table(
    caption: str,
    columns: Sequence[tuple[str, str]],
    rows: Iterable[dict[str, Any]],
) -> html.Details:
    materialized = list(rows)
    return html.Details(
        className="table-alternative",
        children=[
            html.Summary("View evidence table"),
            html.Div(
                className="table-scroll",
                children=html.Table(
                    [
                        html.Caption(caption),
                        html.Thead(
                            html.Tr(
                                [html.Th(label, scope="col") for _, label in columns]
                            )
                        ),
                        html.Tbody(
                            [
                                html.Tr(
                                    [
                                        html.Td(format_number(row.get(key)))
                                        for key, _ in columns
                                    ]
                                )
                                for row in materialized
                            ]
                        ),
                    ]
                ),
            ),
        ],
    )


def chart_record(
    title: str,
    description: str,
    figure: Figure,
    columns: Sequence[tuple[str, str]],
    rows: Iterable[dict[str, Any]],
    *,
    chart_id: str,
) -> html.Section:
    return html.Section(
        className="chart-record",
        **{"aria-labelledby": f"{chart_id}-title"},
        children=[
            html.Div(
                [html.H2(title, id=f"{chart_id}-title"), html.P(description)],
                className="record-heading",
            ),
            html.Div(
                dcc.Graph(
                    id=chart_id,
                    figure=figure,
                    config={"displayModeBar": False, "responsive": True},
                    className="decision-chart",
                ),
                role="img",
                **{"aria-label": description},
            ),
            data_table(f"Text alternative for {title}", columns, rows),
        ],
    )


def methodology(children: list[Any]) -> html.Details:
    return html.Details(
        className="methodology",
        children=[html.Summary("Methodology and limitations"), *children],
    )


def empty_state(recovery: str) -> html.Section:
    return html.Section(
        className="state-panel state-panel--empty",
        role="status",
        children=[html.H2("No evidence matches this view"), html.P(recovery)],
    )


def error_state(message: str) -> html.Section:
    return html.Section(
        className="state-panel state-panel--error",
        role="alert",
        children=[
            html.H2("Evidence temporarily unavailable"),
            html.P(message),
            dcc.Link("Retry", href="/", className="primary-link retry-link"),
        ],
    )
