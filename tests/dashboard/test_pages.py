from __future__ import annotations

import json
from typing import Any

from dash import Dash

from api.schemas import (
    AttributionResponse,
    AudienceQualityResponse,
    CohortsResponse,
    Evidence,
    FunnelResponse,
    IntegrationHealthResponse,
    KpisResponse,
    Provenance,
    SourceItem,
    SourcesResponse,
)
from dashboard.api_client import DashboardAPIClient
from dashboard.app import create_app, nav_classes
from dashboard.pages import (
    acquisition,
    integration_health,
    journeys,
    scenarios,
    summary,
)


def _text(component: Any) -> str:
    """Serialize a real Dash component tree and expose its rendered copy."""
    return json.dumps(component.to_plotly_json(), default=str)


def _evidence(kind: str = "public_observed") -> Evidence:
    return Evidence(
        evidence_type=kind,
        source_date_or_window=(
            "2020-11-01 through 2021-01-31"
            if kind == "public_observed"
            else "deterministic scenario seed 20260910"
        ),
        provenance=Provenance(artifact="reviewed fixture", sha256="a" * 64),
        limitations=["Educational evidence; do not generalize to customer outcomes."],
    )


def _funnel() -> FunnelResponse:
    return FunnelResponse(
        page=1,
        page_size=50,
        total=1,
        evidence=_evidence(),
        items=[
            {
                "date": "2020-11-01",
                "channel_source": "google",
                "channel_medium": "organic",
                "measured_sessions": 120,
                "views": 100,
                "engaged_sessions": 75,
                "add_to_carts": 18,
                "checkouts": 10,
                "purchases": 5,
            }
        ],
    )


def _cohorts() -> CohortsResponse:
    return CohortsResponse(
        page=1,
        page_size=50,
        total=1,
        evidence=_evidence(),
        items=[
            {
                "cohort_date": "2020-11-01",
                "activity_date": "2020-11-08",
                "days_since_acquisition": 7,
                "cohort_users": 1000,
                "retained_users": 20,
                "measured_sessions": 25,
                "cohort_definition": "First touch within source window",
            }
        ],
    )


def test_summary_labels_evidence_types_and_causal_boundary() -> None:
    page = summary.layout(
        KpisResponse(
            page=1,
            page_size=100,
            total=2,
            evidence=_evidence(),
            items=[
                {
                    "name": "funnel",
                    "values": {
                        "views": 333_683,
                        "engaged_sessions": 250_206,
                        "purchases": 2_847,
                    },
                },
                {
                    "name": "day_7_retention",
                    "values": {"rate": 0.006751, "retained_users": 1_611},
                },
            ],
        ),
        SourcesResponse(
            page=1,
            page_size=100,
            total=2,
            boundary="Evidence types are intentionally separate.",
            items=[
                SourceItem(
                    name="Google Analytics 4 public sample",
                    description="Reviewed aggregates",
                    evidence=_evidence(),
                ),
                SourceItem(
                    name="Deterministic integration demonstrations",
                    description="Synthetic records",
                    evidence=_evidence("synthetic"),
                ),
            ],
        ),
    )
    text = _text(page)
    assert "Public GA4 evidence" in text
    assert "Synthetic integration demonstration" in text
    assert "Attribution is descriptive, not causal" in text
    assert "2020-11-01 through 2021-01-31" in text
    assert "View evidence table" in text


def test_decision_pages_expose_chart_alternatives_and_methodology() -> None:
    attribution = AttributionResponse(
        page=1,
        page_size=100,
        total=1,
        evidence=_evidence(),
        items=[
            {
                "model": "first_touch",
                "conversion_credit_total": 3230.0,
                "top_channel_credits": {"google / organic": 1284.0},
                "interpretation": "descriptive attribution; not causal",
            }
        ],
    )
    audience = AudienceQualityResponse(
        page=1,
        page_size=100,
        total=1,
        evidence=_evidence("synthetic"),
        items=[
            {
                "metric": "consent_eligible_candidates",
                "numerator": 80,
                "denominator": 100,
                "rate": 0.8,
            }
        ],
    )
    health = IntegrationHealthResponse(
        page=1,
        page_size=100,
        total=1,
        evidence=_evidence("synthetic"),
        items=[
            {
                "metric": "delivery_success_rate",
                "numerator": 72,
                "denominator": 80,
                "rate": 0.9,
            }
        ],
    )
    pages = [
        acquisition.layout(_funnel(), _cohorts()),
        journeys.layout(_funnel(), attribution),
        integration_health.layout(audience, health),
        scenarios.layout(),
    ]
    for page in pages:
        text = _text(page)
        assert "Methodology" in text
        assert "View evidence table" in text
    assert "descriptive, not causal" in _text(pages[1]).lower()
    assert "Synthetic" in _text(pages[2])
    assert "Synthetic planning demonstration" in _text(pages[3])


def test_empty_and_error_states_are_explicit_and_actionable() -> None:
    empty = acquisition.layout(
        FunnelResponse(page=1, page_size=50, total=0, items=[], evidence=_evidence()),
        CohortsResponse(page=1, page_size=50, total=0, items=[], evidence=_evidence()),
    )
    assert "No evidence matches this view" in _text(empty)
    assert "Reset the date range" in _text(empty)

    error = summary.error_layout("The analytics API could not be reached.")
    assert "Evidence temporarily unavailable" in _text(error)
    assert "Retry" in _text(error)


def test_app_registers_five_keyboard_navigable_decision_routes() -> None:
    app = create_app(load_data=False)
    assert isinstance(app, Dash)
    client = app.server.test_client()
    index = client.get("/")
    assert index.status_code == 200
    layout_response = client.get("/_dash-layout")
    assert layout_response.status_code == 200
    layout_text = layout_response.get_data(as_text=True)
    for label in (
        "Summary",
        "Acquisition",
        "Journeys",
        "Integration health",
        "Scenarios",
    ):
        assert label in layout_text
    assert "Skip to decision" in layout_text


def test_route_rendering_depends_only_on_always_present_location() -> None:
    app = create_app(load_data=True)
    route_callback = app.callback_map["decision-content.children"]
    assert route_callback["inputs"] == [{"id": "route", "property": "pathname"}]


def test_navigation_marks_only_the_current_decision_view() -> None:
    classes = nav_classes("/journeys")
    assert classes == (
        "route-link",
        "route-link",
        "route-link route-link--active",
        "route-link",
        "route-link",
    )


def test_methodology_link_uses_configured_api_boundary() -> None:
    app = create_app(
        load_data=False,
        api_client=DashboardAPIClient(base_url="https://api.example.test"),
    )
    assert "https://api.example.test/api/v1/sources" in _text(app.layout)


def test_each_route_exposes_a_matching_keyboard_focus_decision_note() -> None:
    app = create_app(load_data=False)
    text = _text(app.layout)
    for note in (
        "Read the executive call and evidence boundaries.",
        "Compare channel quality and cohort return.",
        "Inspect funnel loss and descriptive attribution.",
        "Review synthetic consent, match, and delivery checks.",
        "Stress-test a synthetic budget allocation.",
    ):
        assert note in text
