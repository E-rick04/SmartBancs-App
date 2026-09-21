import pytest
from fastapi.testclient import TestClient

from ai_service import main as ai_main
from app import worker


@pytest.fixture
def ai_client(monkeypatch):
    monkeypatch.setattr(ai_main.time, "sleep", lambda _: None)
    with TestClient(ai_main.app) as client:
        yield client


@pytest.mark.parametrize(
    ("amount", "recent_count", "recent_total", "expected_level", "action"),
    [
        ("20.00", 0, "0.00", "LOW", "Registra la transferencia"),
        ("150.00", 0, "0.00", "MEDIUM", "Revisa cómo afecta"),
        ("800.00", 2, "300.00", "HIGH", "El total de movimientos"),
    ],
)
def test_transfer_recommendation_levels(ai_client, amount, recent_count, recent_total, expected_level, action):
    response = ai_client.post("/recommend", json={
        "transaction_id": 10, "amount": amount, "currency": "USD",
        "recent_count_24h": recent_count, "recent_total_24h": recent_total,
    })
    assert response.status_code == 200
    assert response.json()["attention_level"] == expected_level
    assert action in response.json()["recommendation"]


def test_ai_api_rejects_invalid_transfer_input(ai_client):
    response = ai_client.post("/recommend", json={"transaction_id": 1, "amount": "-1", "currency": "USD"})
    assert response.status_code == 422


def test_etl_api_and_worker_recommendation(api_environment, ai_client, monkeypatch):
    api_client, session_factory = api_environment
    start = api_client.post("/etl/run")
    assert start.status_code == 200
    run = start.json()
    assert run["summary"]["input_rows"] == 50
    assert run["summary"]["valid_rows"] == 31
    assert run["summary"]["rejected_rows"] == 19
    assert run["summary"]["duplicates"] == 4
    assert run["summary"]["issues"]["missing_transaction_id"] == 2
    assert run["summary"]["issues"]["missing_or_invalid_amount"] == 3
    assert run["summary"]["issues"]["non_positive_amount"] == 4
    assert run["summary"]["issues"]["invalid_date"] == 4
    assert run["summary"]["issues"]["invalid_currency"] == 3
    assert run["recommendation_status"] == "PENDIENTE"

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker.requests, "post", lambda url, json, timeout: ai_client.post("/recommend/etl", json=json))
    claimed = worker.claim_etl_run()
    assert claimed[0] == run["run_id"]
    worker.process_etl_run(claimed)

    completed = api_client.get(f"/etl/runs/{run['run_id']}")
    assert completed.status_code == 200
    result = completed.json()
    assert result["recommendation_status"] == "COMPLETADO"
    assert "montos faltantes" in result["recommendation"]
    assert "fechas inválidas" in result["recommendation"]
    assert "ID duplicados" in result["recommendation"]
    assert result["model_version"] == "etl-rules-v1"


def test_transfer_workers_finish_bancs_and_ai(api_environment, ai_client, monkeypatch):
    api_client, session_factory = api_environment
    created = api_client.post("/transactions", headers={"Idempotency-Key": "workers-1"}, json={
        "source_account": "CUEN_001", "destination_account": "CUEN_002",
        "amount": "100.00", "currency": "USD",
    })
    assert created.status_code == 200
    transaction_id = created.json()["transaction_id"]

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker.time, "sleep", lambda _: None)
    monkeypatch.setattr(worker.requests, "post", lambda url, json, timeout: ai_client.post("/recommend", json=json))
    monkeypatch.setattr(worker, "EVENT_TYPE", "BANCS")
    worker.process_event(worker.claim_event())
    monkeypatch.setattr(worker, "EVENT_TYPE", "IA")
    worker.process_event(worker.claim_event())

    detail = api_client.get(f"/transactions/{transaction_id}").json()
    assert detail["bancs_sync_status"] == "COMPLETADO"
    assert detail["bancs_reference"] == f"BANCS-{transaction_id:06d}"
    recommendation = api_client.get(f"/transactions/{transaction_id}/recommendation")
    assert recommendation.status_code == 200
    assert "Revisa cómo afecta" in recommendation.json()["recommendation"]


def test_etl_recommendation_when_all_rows_are_valid(ai_client):
    response = ai_client.post("/recommend/etl", json={
        "run_id": 2, "input_rows": 3, "valid_rows": 3, "rejected_rows": 0, "issues": {},
    })
    assert response.status_code == 200
    assert "pasaron la validación" in response.json()["recommendation"]
