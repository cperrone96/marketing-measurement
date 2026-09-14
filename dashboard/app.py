"""Plotly Dash application for the marketing measurement decision studio."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from dash import Dash, Input, Output, State, dcc, html

from dashboard.api_client import DashboardAPIClient, DashboardAPIError
from dashboard.components import error_state
from dashboard.pages import (
    acquisition,
    integration_health,
    journeys,
    scenarios,
    summary,
)

ROUTES = (
    ("/", "Summary", "Read the executive call and evidence boundaries."),
    (
        "/acquisition",
        "Acquisition",
        "Compare channel quality and cohort return.",
    ),
    ("/journeys", "Journeys", "Inspect funnel loss and descriptive attribution."),
    (
        "/integration-health",
        "Integration health",
        "Review synthetic consent, match, and delivery checks.",
    ),
    ("/scenarios", "Scenarios", "Stress-test a synthetic budget allocation."),
)


def nav_classes(pathname: str | None) -> tuple[str, ...]:
    current = pathname or "/"
    return tuple(
        "route-link route-link--active" if path == current else "route-link"
        for path, _label, _note in ROUTES
    )


def create_app(
    *, load_data: bool = True, api_client: DashboardAPIClient | None = None
) -> Dash:
    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="Marketing Measurement Decision Studio",
    )
    api = api_client or DashboardAPIClient()
    app.layout = html.Div(
        className="app-shell",
        children=[
            dcc.Location(id="route", refresh=False),
            html.A("Skip to decision", href="#decision-content", className="skip-link"),
            html.Header(
                className="masthead",
                children=[
                    html.Div(
                        [
                            html.Strong("MEASURE / DECIDE"),
                            html.Span("Public evidence + synthetic planning"),
                        ],
                        className="wordmark",
                    ),
                    html.Nav(
                        [
                            dcc.Link(
                                [
                                    html.Span(label),
                                    html.Span(
                                        note,
                                        className="route-focus-note",
                                    ),
                                ],
                                href=path,
                                id=f"nav-{label.lower().replace(' ', '-')}",
                                className="route-link",
                            )
                            for path, label, note in ROUTES
                        ],
                        **{"aria-label": "Decision views"},
                    ),
                ],
            ),
            dcc.Loading(
                type="circle",
                color="#5b4c91",
                children=html.Main(
                    id="decision-content",
                    tabIndex=-1,
                    children=(
                        html.Section(
                            [
                                html.H1("Decision dashboard"),
                                html.P("Choose a decision view from the navigation."),
                            ],
                            className="page loading-placeholder",
                        )
                        if not load_data
                        else html.Div()
                    ),
                ),
            ),
            html.Footer(
                [
                    html.P(
                        "Educational portfolio • Public observed evidence remains separate from synthetic demonstrations."
                    ),
                    html.A(
                        "Read source methodology",
                        href=f"{api.base_url}/api/v1/sources",
                    ),
                ]
            ),
        ],
    )

    if load_data:

        @app.callback(
            [
                Output(f"nav-{label.lower().replace(' ', '-')}", "className")
                for _path, label, _note in ROUTES
            ],
            Input("route", "pathname"),
        )
        def mark_active_route(pathname: str | None) -> tuple[str, ...]:
            return nav_classes(pathname)

        @app.callback(
            Output("decision-content", "children"),
            Input("route", "pathname"),
        )
        def render_route(pathname: str | None) -> html.Div:
            try:
                if pathname == "/acquisition":
                    return acquisition.layout(api.funnel(), api.cohorts(), api.kpis())
                if pathname == "/journeys":
                    return journeys.layout(api.funnel(), api.attribution(), api.kpis())
                if pathname == "/integration-health":
                    return integration_health.layout(
                        api.audience_quality(), api.integration_health()
                    )
                if pathname == "/scenarios":
                    return scenarios.layout()
                return summary.layout(api.kpis(), api.sources())
            except DashboardAPIError as error:
                return summary.error_layout(str(error))

        @app.callback(
            Output("scenario-result", "children"),
            Input("run-scenario", "n_clicks"),
            State("scenario-budget", "value"),
            prevent_initial_call=True,
        )
        def run_scenario(
            _clicks: int, budget: float | str | None
        ) -> html.Div | html.Section:
            try:
                amount = Decimal(str(budget))
                if amount <= 0:
                    raise InvalidOperation
                return scenarios.result_layout(api.budget_scenario(amount))
            except (InvalidOperation, DashboardAPIError):
                return error_state(
                    "Enter a positive budget and retry the synthetic scenario."
                )

    return app


app = create_app()
server = app.server


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050)
