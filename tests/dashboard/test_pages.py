from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from dash import Dash, dcc

from api.schemas import (
    AttributionResponse,
    AudienceQualityResponse,
    BudgetScenarioResponse,
    CohortsResponse,
    Evidence,
    FunnelResponse,
    IntegrationHealthResponse,
    KpisResponse,
    Provenance,
    SourceItem,
    SourcesResponse,
)
from dashboard.api_client import DashboardAPIClient, DashboardAPIError
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


def _graph(component: Any, graph_id: str) -> dcc.Graph:
    if isinstance(component, dcc.Graph) and component.id == graph_id:
        return component
    children = getattr(component, "children", None)
    candidates = children if isinstance(children, list) else [children]
    for child in candidates:
        if child is None:
            continue
        try:
            return _graph(child, graph_id)
        except LookupError:
            pass
    raise LookupError(graph_id)


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
        decision_summary={
            "coverage": "full_filtered_window",
            "stages": {
                "views": 100,
                "engaged_sessions": 75,
                "add_to_carts": 18,
                "checkouts": 10,
                "purchases": 5,
            },
            "channels": [
                {
                    "channel": "google / organic",
                    "views": 100,
                    "engaged_sessions": 75,
                    "purchases": 5,
                }
            ],
        },
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
        decision_summary={
            "coverage": "complete_day_7_cohorts",
            "items": [
                {
                    "cohort_date": "2020-11-01",
                    "days_since_acquisition": 7,
                    "cohort_users": 1000,
                    "retained_users": 20,
                    "retention_rate": 0.02,
                }
            ],
        },
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


def test_dashboard_surfaces_approved_analysis_scope_within_five_pages() -> None:
    kpis = KpisResponse(
        page=1,
        page_size=100,
        total=0,
        items=[],
        evidence=_evidence(),
        analyses=[
            {
                "analysis": name,
                "decision": f"Review {name}",
                "rows": [{"dimension": "example", "sessions": 10, "revenue": 5.0}],
                "evidence": _evidence(),
            }
            for name in (
                "landing_page",
                "device",
                "product_revenue",
                "high_value_journey",
            )
        ],
    )
    acquisition_text = _text(acquisition.layout(_funnel(), _cohorts(), kpis))
    journeys_text = _text(
        journeys.layout(
            _funnel(),
            AttributionResponse(page=1, page_size=100, total=0, items=[], evidence=_evidence()),
            kpis,
        )
    )

    assert "Landing-page performance" in acquisition_text
    assert "Device performance" in acquisition_text
    assert "Product and revenue performance" in journeys_text
    assert "High-value journeys" in journeys_text


def test_analysis_records_render_their_own_portfolio_provenance_not_funnel_provenance() -> None:
    portfolio_evidence = Evidence(
        evidence_type="public_observed",
        source_date_or_window="2020-11-01 through 2021-01-31",
        provenance=Provenance(
            artifact="PORTFOLIO_MARKER", sha256="portfolio-hash-marker"
        ),
        limitations=["Portfolio limitation."],
    )
    funnel = _funnel()
    funnel.evidence.provenance.artifact = "FUNNEL_MARKER"
    funnel.evidence.provenance.sha256 = "funnel-hash-marker"
    kpis = KpisResponse(
        page=1,
        page_size=100,
        total=0,
        items=[],
        evidence=_evidence(),
        analyses=[
            {
                "analysis": name,
                "decision": "Inspect this result.",
                "rows": [{"dimension": "example", "sessions": 10, "revenue": 5.0}],
                "evidence": portfolio_evidence,
            }
            for name in (
                "landing_page",
                "device",
                "product_revenue",
                "high_value_journey",
            )
        ],
    )
    acquisition_text = _text(acquisition.layout(funnel, _cohorts(), kpis))
    journeys_text = _text(
        journeys.layout(
            funnel,
            AttributionResponse(page=1, page_size=100, total=0, items=[], evidence=_evidence()),
            kpis,
        )
    )

    for rendered in (acquisition_text, journeys_text):
        assert "PORTFOLIO_MARKER" in rendered
        assert "portfolio-hash-marker" in rendered
    assert "FUNNEL_MARKER" in acquisition_text
    assert "FUNNEL_MARKER" in journeys_text


def test_empty_and_error_states_are_explicit_and_actionable() -> None:
    empty = acquisition.layout(
        FunnelResponse(
            page=1,
            page_size=50,
            total=0,
            items=[],
            decision_summary={
                "coverage": "full_filtered_window",
                "stages": {
                    "views": 0,
                    "engaged_sessions": 0,
                    "add_to_carts": 0,
                    "checkouts": 0,
                    "purchases": 0,
                },
                "channels": [],
            },
            evidence=_evidence(),
        ),
        CohortsResponse(
            page=1,
            page_size=50,
            total=0,
            items=[],
            decision_summary={
                "coverage": "complete_day_7_cohorts",
                "items": [],
            },
            evidence=_evidence(),
        ),
    )
    assert "No evidence matches this view" in _text(empty)
    assert "Reset the date range" in _text(empty)

    error = summary.error_layout("The analytics API could not be reached.")
    assert "Evidence temporarily unavailable" in _text(error)
    assert "Retry" in _text(error)


def test_summary_treats_valid_empty_kpis_and_sources_as_an_empty_state() -> None:
    page = summary.layout(
        KpisResponse(page=1, page_size=100, total=0, items=[], evidence=_evidence()),
        SourcesResponse(
            page=1,
            page_size=100,
            total=0,
            boundary="Evidence types are intentionally separate.",
            items=[],
        ),
    )

    text = _text(page)
    assert "No evidence matches this view" in text
    assert "Observed journey tally" not in text


def test_summary_handles_missing_source_register_without_key_error() -> None:
    page = summary.layout(
        KpisResponse(
            page=1,
            page_size=100,
            total=1,
            evidence=_evidence(),
            items=[
                {
                    "name": "funnel",
                    "values": {
                        "views": 100,
                        "engaged_sessions": 75,
                        "purchases": 5,
                    },
                }
            ],
        ),
        SourcesResponse(
            page=1,
            page_size=100,
            total=0,
            boundary="Evidence types are intentionally separate.",
            items=[],
        ),
    )

    text = _text(page)
    assert "Public GA4 evidence" in text
    assert "Source register is empty" in text


def test_scenario_result_renders_sensitivity_chart_and_text_alternative() -> None:
    result = BudgetScenarioResponse(
        allocations={"channel_aurora": "70.00", "channel_birch": "30.00"},
        total_budget="100.00",
        estimated_incremental_value="117.00",
        assumptions=["Synthetic planning assumption."],
        sensitivity=[
            {
                "scenario": "channel_aurora_down_20pct",
                "varied_channel": "channel_aurora",
                "value_multiplier": 0.8,
                "estimated_incremental_value": "97.40",
                "ranking_changed_from_baseline": True,
                "allocation_changed_from_baseline": True,
                "decision_summary": "The preferred allocation changes under this stress test.",
            }
        ],
        robustness_summary="One tested assumption changes the preferred allocation.",
        experiment={
            "evidence_type": "synthetic",
            "evidence": _evidence("synthetic"),
            "analysis_population": "all randomized synthetic audience candidates (intent-to-treat)",
            "baseline_rate": 0.062376,
            "minimum_detectable_effect": 0.015594,
            "planned_sample_per_arm": 4209,
            "observed_sample_per_arm": 100,
            "itt_effect": 0.01,
            "confidence_interval": [-0.02, 0.04],
            "confidence_level": 0.95,
            "conclusion": "inconclusive synthetic demonstration",
        },
        evidence=_evidence("synthetic"),
    )

    text = _text(scenarios.result_layout(result))
    assert "Sensitivity decision evidence" in text
    assert "Channel Aurora Down 20Pct" in text
    assert "The preferred allocation changes under this stress test." in text
    assert text.count("View evidence table") == 3
    assert "reviewed fixture" in text


def test_production_client_validates_full_sample_decision_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/funnel"
        assert request.url.params["page_size"] == "1"
        return httpx.Response(
            200,
            json={
                "page": 1,
                "page_size": 1,
                "total": 2351,
                "items": [],
                "decision_summary": {
                    "coverage": "full_filtered_window",
                    "stages": {
                        "views": 333683,
                        "engaged_sessions": 250206,
                        "add_to_carts": 14919,
                        "checkouts": 5956,
                        "purchases": 2847,
                    },
                    "channels": [],
                },
                "evidence": _evidence().model_dump(mode="json"),
            },
        )

    api = DashboardAPIClient(
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    response = api.funnel()
    assert response.decision_summary.stages.views == 333_683
    assert response.items == []
    attribution = AttributionResponse(
        page=1,
        page_size=100,
        total=0,
        items=[],
        evidence=_evidence(),
    )
    page = journeys.layout(response, attribution)
    graph = _graph(page, "journey-funnel")
    assert list(graph.figure.data[0].x) == [
        333_683,
        250_206,
        14_919,
        5_956,
        2_847,
    ]


def test_production_client_rejects_missing_decision_summary() -> None:
    api = DashboardAPIClient(
        base_url="https://api.example.test",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "page": 1,
                    "page_size": 1,
                    "total": 1,
                    "items": [],
                    "evidence": _evidence().model_dump(mode="json"),
                },
            )
        ),
    )

    with pytest.raises(DashboardAPIError):
        api.funnel()


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
