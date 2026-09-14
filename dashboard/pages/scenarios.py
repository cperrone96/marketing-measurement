"""Synthetic budget scenario controls and result renderer."""

from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from api.schemas import BudgetScenarioResponse
from dashboard.components import (
    chart_record,
    decision_header,
    evidence_strip,
    methodology,
)


def layout() -> html.Div:
    return html.Div(
        className="page",
        children=[
            decision_header(
                "Budget scenario desk",
                "Stress-test a planning allocation before treating it as a recommendation.",
                "Change the total budget, run the deterministic scenario, and compare sensitivity—not just the baseline ranking.",
            ),
            html.Section(
                className="scenario-control",
                children=[
                    html.Label("Total demonstration budget", htmlFor="scenario-budget"),
                    dcc.Input(
                        id="scenario-budget",
                        type="number",
                        min=100,
                        step=100,
                        value=10000,
                        inputMode="decimal",
                    ),
                    html.Button(
                        "Run synthetic scenario",
                        id="run-scenario",
                        n_clicks=0,
                        type="button",
                    ),
                ],
            ),
            html.Div(
                [
                    html.P(
                        "Synthetic planning demonstration",
                        className="evidence-strip__label",
                    ),
                    html.P(
                        "Run the scenario to produce a cent-exact allocation and its sensitivity record."
                    ),
                    html.Details(
                        [
                            html.Summary("View evidence table"),
                            html.P(
                                "No scenario result yet. Run the demonstration to populate this table."
                            ),
                        ]
                    ),
                ],
                id="scenario-result",
                className="scenario-result",
                role="status",
                **{"aria-live": "polite"},
            ),
            methodology(
                [
                    html.P("All scenario values are synthetic and deterministic."),
                    html.P(
                        "The optimizer respects channel minimums, capacities, and cent-exact total budget constraints."
                    ),
                ]
            ),
        ],
    )


def result_layout(result: BudgetScenarioResponse) -> html.Div:
    rows = [
        {"channel": channel.replace("_", " ").title(), "allocation": amount}
        for channel, amount in result.allocations.items()
    ]
    figure = go.Figure(
        go.Bar(
            x=[row["channel"] for row in rows],
            y=[float(row["allocation"]) for row in rows],
            marker_color=["#5b4c91", "#8d77c2"][: len(rows)],
        )
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f5f0e6",
        font={"color": "#152b31", "family": "IBM Plex Mono, Menlo, monospace"},
        margin={"l": 70, "r": 30, "t": 18, "b": 70},
        height=330,
        yaxis_title="Synthetic allocation",
        showlegend=False,
    )
    figure.update_yaxes(gridcolor="#c9c1b1", tickprefix="$", zeroline=False)
    sensitivity_rows = [
        {
            "scenario": item.scenario.replace("_", " ").title(),
            "varied_channel": item.varied_channel.replace("_", " ").title(),
            "value_multiplier": item.value_multiplier,
            "estimated_incremental_value": item.estimated_incremental_value,
            "ranking_changed": "Yes" if item.ranking_changed_from_baseline else "No",
            "allocation_changed": (
                "Yes" if item.allocation_changed_from_baseline else "No"
            ),
            "decision_summary": item.decision_summary,
        }
        for item in result.sensitivity
    ]
    sensitivity_figure = go.Figure(
        go.Bar(
            x=[row["scenario"] for row in sensitivity_rows],
            y=[float(row["estimated_incremental_value"]) for row in sensitivity_rows],
            marker_color="#8d77c2",
        )
    )
    sensitivity_figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#f5f0e6",
        font={"color": "#152b31", "family": "IBM Plex Mono, Menlo, monospace"},
        margin={"l": 70, "r": 30, "t": 18, "b": 100},
        height=360,
        yaxis_title="Estimated synthetic value",
        showlegend=False,
    )
    sensitivity_figure.update_xaxes(gridcolor="#c9c1b1", tickangle=-20)
    sensitivity_figure.update_yaxes(
        gridcolor="#c9c1b1", tickprefix="$", zeroline=False
    )
    return html.Div(
        [
            evidence_strip(result.evidence),
            chart_record(
                "Scenario allocation",
                result.robustness_summary,
                figure,
                [("channel", "Synthetic channel"), ("allocation", "Allocation")],
                rows,
                chart_id="scenario-allocation",
            ),
            html.P(
                f"Estimated incremental value: ${result.estimated_incremental_value}"
            ),
            chart_record(
                "Sensitivity decision evidence",
                result.robustness_summary,
                sensitivity_figure,
                [
                    ("scenario", "Stress-test scenario"),
                    ("varied_channel", "Varied channel"),
                    ("value_multiplier", "Value multiplier"),
                    ("estimated_incremental_value", "Estimated incremental value"),
                    ("ranking_changed", "Ranking changed"),
                    ("allocation_changed", "Allocation changed"),
                    ("decision_summary", "Decision summary"),
                ],
                sensitivity_rows,
                chart_id="scenario-sensitivity",
            ),
            html.Ul([html.Li(item) for item in result.assumptions]),
            html.Section(
                [
                    html.H2("Randomized experiment scenario"),
                    html.P(result.experiment.conclusion),
                    html.P(
                        f"Marginal ITT design: {result.experiment.planned_sample_per_arm:,} "
                        f"planned per arm; {result.experiment.observed_sample_per_arm:,} "
                        "synthetic records observed per arm."
                    ),
                    html.Details(
                        [
                            html.Summary("View evidence table"),
                            html.Table(
                                [
                                    html.Tbody(
                                        [
                                            html.Tr([html.Th("Analysis population"), html.Td(result.experiment.analysis_population)]),
                                            html.Tr([html.Th("ITT effect"), html.Td(f"{result.experiment.itt_effect:.4f}")]),
                                            html.Tr([html.Th("Confidence level"), html.Td(f"{result.experiment.confidence_level:.0%}")]),
                                        ]
                                    )
                                ]
                            ),
                        ]
                    ),
                ],
                className="analysis-record synthetic-lane",
            ),
        ]
    )
