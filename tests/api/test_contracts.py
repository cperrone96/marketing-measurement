"""Public contract tests for the versioned marketing-measurement API."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest

from api.main import app
from api.repository import ArtifactRepository
from api.services import MarketingMeasurementService


class APIClient:
    """Small synchronous adapter over httpx's in-process ASGI transport."""

    def request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: object) -> httpx.Response:
        return self.request("POST", path, **kwargs)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def assert_evidence(response: dict[str, object], evidence_type: str) -> None:
    evidence = response["evidence"]
    assert isinstance(evidence, dict)
    assert evidence["evidence_type"] == evidence_type
    assert evidence["source_date_or_window"]
    assert evidence["provenance"]["sha256"]
    assert evidence["limitations"]


def test_health_contract(client: APIClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert set(response.json()) >= {"status", "version", "database"}


def test_sources_explicitly_separate_observed_and_synthetic_evidence(
    client: APIClient,
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
    client: APIClient, path: str, evidence_type: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert {"items", "page", "page_size", "total", "evidence"} <= set(payload)
    assert payload["page"] == 1
    assert payload["total"] >= len(payload["items"])
    assert_evidence(payload, evidence_type)


def test_funnel_accepts_bounded_dates_and_paginates_first_last_empty_and_oversized_pages(
    client: APIClient,
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


def test_funnel_decision_summary_covers_full_window_on_every_page(
    client: APIClient,
) -> None:
    first = client.get("/api/v1/funnel", params={"page": 1, "page_size": 1})
    second = client.get("/api/v1/funnel", params={"page": 2, "page_size": 1})

    assert first.status_code == second.status_code == 200
    assert first.json()["total"] > len(first.json()["items"])
    assert first.json()["decision_summary"] == second.json()["decision_summary"]
    assert first.json()["decision_summary"]["coverage"] == "full_filtered_window"
    assert first.json()["decision_summary"]["stages"] == {
        "views": 333_683,
        "engaged_sessions": 250_206,
        "add_to_carts": 14_919,
        "checkouts": 5_956,
        "purchases": 2_847,
    }
    assert first.json()["decision_summary"]["channels"]


def test_kpis_and_funnel_publish_one_full_window_truth(client: APIClient) -> None:
    kpis = client.get("/api/v1/kpis").json()
    funnel = client.get("/api/v1/funnel?page_size=1").json()
    by_name = {item["name"]: item["values"] for item in kpis["items"]}

    assert funnel["decision_summary"]["stages"] == {
        key: by_name["funnel"][key]
        for key in ("views", "engaged_sessions", "add_to_carts", "checkouts", "purchases")
    }


def test_cohort_decision_summary_covers_all_complete_day_7_cohorts_on_every_page(
    client: APIClient,
) -> None:
    first = client.get("/api/v1/cohorts", params={"page": 1, "page_size": 1})
    second = client.get("/api/v1/cohorts", params={"page": 2, "page_size": 1})

    assert first.status_code == second.status_code == 200
    assert first.json()["total"] > len(first.json()["items"])
    assert first.json()["decision_summary"] == second.json()["decision_summary"]
    summary = first.json()["decision_summary"]
    assert summary["coverage"] == "complete_day_7_cohorts"
    assert len(summary["items"]) == 85
    assert all(item["days_since_acquisition"] == 7 for item in summary["items"])


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
    client: APIClient, path: str
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
    client: APIClient, params: dict[str, object]
) -> None:
    response = client.get("/api/v1/cohorts", params=params)

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message", "details"}


def test_model_contract_is_reviewed_evidence_without_model_object(client: APIClient) -> None:
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
    client: APIClient, payload: object
) -> None:
    response = client.post("/api/v1/scenarios/budget", json=payload)

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message", "details"}


def test_budget_honors_cent_precision_minimum_capacity_and_synthetic_boundary(
    client: APIClient,
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
    assert body["allocations"] == {"channel_aurora": "0.70", "channel_birch": "0.30"}
    assert body["total_budget"] == "1.00"
    assert body["estimated_incremental_value"] == "1.31"
    assert_evidence(body, "synthetic")


def test_budget_rejects_capacity_failure(client: APIClient) -> None:
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


def test_budget_accepts_exact_minimum_and_capacity_boundaries(client: APIClient) -> None:
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
        "channel_aurora": "0.10",
        "channel_birch": "0.20",
    }


def test_budget_preserves_extreme_valid_cents_exactly(client: APIClient) -> None:
    amount = "90071992547409.93"
    response = client.post(
        "/api/v1/scenarios/budget",
        json={
            "total_budget": amount,
            "minimums": {"channel_aurora": amount},
            "capacities": {"channel_aurora": amount},
            "expected_incremental_value": {"channel_aurora": "1.00"},
        },
    )

    assert response.status_code == 200
    assert response.json()["total_budget"] == amount
    assert response.json()["allocations"] == {"channel_aurora": amount}
    assert response.json()["estimated_incremental_value"] == amount


def test_budget_extreme_exponent_is_a_structured_422(client: APIClient) -> None:
    response = client.post(
        "/api/v1/scenarios/budget",
        json={
            "total_budget": "1e10000",
            "minimums": {"channel_aurora": "0.00"},
            "capacities": {"channel_aurora": "1e10000"},
            "expected_incremental_value": {"channel_aurora": "1.00"},
        },
    )

    assert response.status_code == 422
    assert set(response.json()) == {"code", "message", "details"}


@pytest.mark.parametrize(
    ("method", "path", "code", "message"),
    [
        ("GET", "/api/v1/not-a-route", "not_found", "Requested resource was not found"),
        (
            "POST",
            "/api/v1/health",
            "method_not_allowed",
            "Requested method is not allowed",
        ),
    ],
)
def test_http_errors_use_safe_structured_contracts(
    client: APIClient, method: str, path: str, code: str, message: str
) -> None:
    response = client.request(method, path)

    assert response.status_code in {404, 405}
    assert response.json() == {
        "code": code,
        "message": message,
        "details": {"status": response.status_code},
    }


def test_synthetic_provenance_hashes_the_committed_generator_artifact(
    client: APIClient,
) -> None:
    response = client.get("/api/v1/integrations/health")
    expected = hashlib.sha256(
        Path("src/marketing_measurement/simulation/integration.py").read_bytes()
    ).hexdigest()

    assert response.status_code == 200
    assert response.json()["evidence"]["provenance"] == {
        "artifact": "deterministic integration generator",
        "sha256": expected,
    }


def test_synthetic_provenance_changes_when_its_generator_artifact_changes(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "src/marketing_measurement/simulation/integration.py"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("first generator", encoding="utf-8")
    service = MarketingMeasurementService(ArtifactRepository(tmp_path))
    first = service.synthetic_evidence("integration")
    artifact.write_text("changed generator", encoding="utf-8")
    second = service.synthetic_evidence("integration")

    assert first["provenance"]["sha256"] != second["provenance"]["sha256"]


def test_public_kpi_provenance_authenticates_the_returned_summary(client: APIClient) -> None:
    expected = hashlib.sha256(
        Path("data/derived/ga4_public_sample/findings_summary.json").read_bytes()
    ).hexdigest()
    response = client.get("/api/v1/kpis")

    assert response.json()["evidence"]["provenance"] == {
        "artifact": "reviewed findings summary",
        "sha256": expected,
    }


def test_kpis_expose_reviewed_landing_device_product_revenue_and_journey_analysis(
    client: APIClient,
) -> None:
    response = client.get("/api/v1/kpis")
    sections = {item["analysis"]: item for item in response.json()["analyses"]}

    assert set(sections) == {
        "landing_page",
        "device",
        "product_revenue",
        "high_value_journey",
    }
    assert all(item["evidence"]["evidence_type"] == "public_observed" for item in sections.values())
    assert all(item["rows"] for item in sections.values())
    assert all(item["decision"] for item in sections.values())


def test_budget_response_includes_aligned_synthetic_experiment_scenario(
    client: APIClient,
) -> None:
    response = client.post(
        "/api/v1/scenarios/budget",
        json={
            "total_budget": "100.00",
            "minimums": {"channel_aurora": "0.00"},
            "capacities": {"channel_aurora": "100.00"},
            "expected_incremental_value": {"channel_aurora": "1.00"},
        },
    )
    experiment = response.json()["experiment"]

    assert experiment["evidence_type"] == "synthetic"
    assert experiment["planned_sample_per_arm"] == 4209
    assert experiment["analysis_population"].startswith("all randomized")
    assert experiment["conclusion"].startswith("inconclusive")
    assert experiment["evidence"]["provenance"]["artifact"] == (
        "src/marketing_measurement/analysis/experiments.py + "
        "src/marketing_measurement/simulation/integration.py composite manifest"
    )
    assert experiment["evidence"]["provenance"]["sha256"] != response.json()[
        "evidence"
    ]["provenance"]["sha256"]


def test_experiment_composite_provenance_changes_independently_from_budget(
    tmp_path: Path,
) -> None:
    experiment = tmp_path / "src/marketing_measurement/analysis/experiments.py"
    integration = tmp_path / "src/marketing_measurement/simulation/integration.py"
    budget = tmp_path / "src/marketing_measurement/analysis/budget.py"
    for path, content in (
        (experiment, "experiment v1"),
        (integration, "integration v1"),
        (budget, "budget v1"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    service = MarketingMeasurementService(ArtifactRepository(tmp_path))

    experiment_before = service.synthetic_evidence("experiment")
    budget_before = service.synthetic_evidence("budget")
    experiment.write_text("experiment v2", encoding="utf-8")
    experiment_after_experiment_change = service.synthetic_evidence("experiment")
    budget_after_experiment_change = service.synthetic_evidence("budget")
    integration.write_text("integration v2", encoding="utf-8")
    experiment_after_integration_change = service.synthetic_evidence("experiment")
    budget_after_integration_change = service.synthetic_evidence("budget")

    experiment_hashes = {
        evidence["provenance"]["sha256"]
        for evidence in (
            experiment_before,
            experiment_after_experiment_change,
            experiment_after_integration_change,
        )
    }
    assert len(experiment_hashes) == 3
    assert budget_before["provenance"]["sha256"] == budget_after_experiment_change[
        "provenance"
    ]["sha256"]
    assert budget_before["provenance"]["sha256"] == budget_after_integration_change[
        "provenance"
    ]["sha256"]
    assert experiment_after_integration_change["provenance"]["sha256"] != (
        budget_after_integration_change["provenance"]["sha256"]
    )


def test_model_response_is_loaded_from_and_hashes_reviewed_output(client: APIClient) -> None:
    artifact = Path("data/derived/ga4_public_sample/conversion_model_evaluation.json")
    expected_payload = __import__("json").loads(artifact.read_text(encoding="utf-8"))
    response = client.get("/api/v1/models/conversion")

    assert response.status_code == 200
    assert {
        key: response.json()[key] for key in expected_payload
    } == expected_payload
    assert response.json()["evidence"]["provenance"] == {
        "artifact": "reviewed conversion model evaluation",
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
    }
