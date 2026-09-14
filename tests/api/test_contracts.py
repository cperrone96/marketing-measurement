"""Public contract tests for the versioned marketing-measurement API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def assert_evidence(response: dict[str, object], evidence_type: str) -> None:
    evidence = response["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["evidence_type"] == evidence_type
    assert evidence["source_date_or_window"]
    assert evidence["provenance"]["sha256"]
    assert evidence["limitations"]


def test_health_contract(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert set(response.json()) >= {"status", "version", "database"}


def test_sources_explicitly_separate_observed_and_synthetic_evidence(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/sources")

    assert response.status_code == 200
    payload = response.json()
    assert payload["boundary"]
    assert {item["evidence"]["evidence_type"] for item in payload["items"]} == {
        "public_observed",
        "synthetic",
    }
    for item in payload["items"]:
        assert_evidence(item, item["evidence"]["evidence_type"])


@pytest.mark.parametrize(
    "path,evidence_type",
    [
        ("/api/v1/kpis", "public_observed"),
        ("/api/v1/funnel", "public_observed"),
        ("/api/v1/cohorts", "public_observed"),
        ("/api/v1/attribution", "public_observed"),
        ("/api/v1/audiences/quality", "synthetic"),
        ("/api/v1/integrations/health", "synthetic"),
    ],
)
def test_collection_contracts_include_paginated_evidence(
    client: TestClient, path: str, evidence_type: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert {"items", "page", "page_size", "total", "evidence"} <= set(payload)
    assert payload["page"] == 1
    assert payload["total"] >= len(payload["items"])
    assert_evidence(payload, evidence_type)


def test_funnel_accepts_bounded_dates_and_paginates_first_last_empty_and_oversized_pages(
    client: TestClient,
) -> None:
    query = {"start_date": "2020-11-01", "end_date": "2021-01-31", "page_size": 1}
    first = client.get("/api/v1/funnel", params=query)
    last = client.get("/api/v1/funnel", params={**query, "page": first.json()["total"]})
    empty = client.get(
        "/api/v1/funnel", params={**query, "page": first.json()["total"] + 1}
    )
    oversized = client.get("/api/v1/funnel", params={**query, "page_size": 101})

    assert first.status_code == last.status_code == empty.status_code == 200
    assert len(first.json()["items"]) == len(last.json()["items"]) == 1
    assert empty.json()["items"] == []
    assert oversized.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/sources",
        "/api/v1/kpis",
        "/api/v1/cohorts",
        "/api/v1/attribution",
        "/api/v1/audiences/quality",
        "/api/v1/integrations/health",
    ],
)
def test_every_collection_supports_first_last_empty_and_oversized_pages(
    client: TestClient, path: str
) -> None:
    first = client.get(path, params={"page": 1, "page_size": 1})
    total = first.json()["total"]
    last = client.get(path, params={"page": total, "page_size": 1})
    empty = client.get(path, params={"page": total + 1, "page_size": 1})
    oversized = client.get(path, params={"page": 1, "page_size": 101})

    assert first.status_code == last.status_code == empty.status_code == 200
    assert len(first.json()["items"]) == len(last.json()["items"]) == 1
    assert empty.json()["items"] == []
    assert oversized.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "2020-10-31"},
        {"end_date": "2021-02-01"},
        {"start_date": "2021-01-02", "end_date": "2021-01-01"},
        {"page": 0},
        {"page_size": 0},
    ],
)
def test_collection_filters_reject_invalid_windows_and_pagination(
    client: TestClient, params: dict[str, object]
) -> None:
    response = client.get("/api/v1/cohorts", params=params)

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message", "details"}


def test_model_contract_is_reviewed_evidence_without_model_object(client: TestClient) -> None:
    response = client.get("/api/v1/models/conversion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_model"] == "logistic_regression"
    assert "model" not in payload
    assert_evidence(payload, "public_observed")


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"total_budget": -1},
        {"total_budget": ["not a number"], "minimums": {"channel_aurora": 0}, "capacities": {"channel_aurora": 1}, "expected_incremental_value": {"channel_aurora": 1}},
        {"total_budget": "1.001", "minimums": {}, "capacities": {}, "expected_incremental_value": {}},
        {"total_budget": 1, "minimums": {"channel_aurora": "0.001"}, "capacities": {"channel_aurora": 1}, "expected_incremental_value": {"channel_aurora": 1}},
        {"total_budget": 1, "minimums": {"channel_aurora": 0}, "capacities": {"channel_aurora": "1.001"}, "expected_incremental_value": {"channel_aurora": 1}},
        {"total_budget": 1, "minimums": {"unknown": 0}, "capacities": {"unknown": 1}, "expected_incremental_value": {"unknown": 1}},
        {"total_budget": 1, "minimums": {"channel_aurora": 0}, "capacities": {"channel_birch": 1}, "expected_incremental_value": {"channel_aurora": 1}},
        {"total_budget": 1, "minimums": {"channel_aurora": "1; DROP TABLE"}, "capacities": {"channel_aurora": 1}, "expected_incremental_value": {"channel_aurora": 1}},
    ],
)
def test_budget_rejects_invalid_inputs_with_structured_errors(
    client: TestClient, payload: object
) -> None:
    response = client.post("/api/v1/scenarios/budget", json=payload)

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message", "details"}


def test_budget_honors_cent_precision_minimum_capacity_and_synthetic_boundary(
    client: TestClient,
) -> None:
    payload = {
        "total_budget": "1.00",
        "minimums": {"channel_aurora": "0.10", "channel_birch": "0.20"},
        "capacities": {"channel_aurora": "0.70", "channel_birch": "0.80"},
        "expected_incremental_value": {"channel_aurora": 1.4, "channel_birch": 1.1},
    }
    response = client.post("/api/v1/scenarios/budget", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["allocations"] == {"channel_aurora": 0.7, "channel_birch": 0.3}
    assert_evidence(body, "synthetic")


def test_budget_rejects_capacity_failure(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scenarios/budget",
        json={
            "total_budget": "1.00",
            "minimums": {"channel_aurora": "0.00"},
            "capacities": {"channel_aurora": "0.99"},
            "expected_incremental_value": {"channel_aurora": 1.0},
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_budget_scenario"


def test_budget_accepts_exact_minimum_and_capacity_boundaries(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scenarios/budget",
        json={
            "total_budget": "0.30",
            "minimums": {"channel_aurora": "0.10", "channel_birch": "0.20"},
            "capacities": {"channel_aurora": "0.10", "channel_birch": "0.20"},
            "expected_incremental_value": {"channel_aurora": 1, "channel_birch": 1},
        },
    )

    assert response.status_code == 200
    assert response.json()["allocations"] == {
        "channel_aurora": 0.1,
        "channel_birch": 0.2,
    }
