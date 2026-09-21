from decimal import Decimal

from sqlalchemy import select

from app.models import OutboxEvent, Transaction


TRANSFER = {
    "source_account": "CUEN_001",
    "destination_account": "CUEN_002",
    "amount": "125.50",
    "currency": "USD",
}


def test_health_and_accounts(api_environment):
    client, _ = api_environment
    assert client.get("/health").json() == {"status": "ok"}
    accounts = client.get("/accounts").json()
    assert [row["account_number"] for row in accounts] == ["CUEN_001", "CUEN_002"]


def test_transfer_is_atomic_and_creates_background_events(api_environment):
    client, session_factory = api_environment
    response = client.post("/transactions", json=TRANSFER, headers={"Idempotency-Key": "transfer-1"})
    assert response.status_code == 200
    transaction_id = response.json()["transaction_id"]
    assert response.json()["status"] == "COMPLETADA"
    assert response.json()["bancs_sync_status"] == "PENDIENTE"

    accounts = {row["account_number"]: Decimal(str(row["balance"])) for row in client.get("/accounts").json()}
    assert accounts == {"CUEN_001": Decimal("874.50"), "CUEN_002": Decimal("625.50")}
    detail = client.get(f"/transactions/{transaction_id}")
    assert detail.status_code == 200
    assert detail.json()["source_account"] == "CUEN_001"
    assert client.get(f"/transactions/{transaction_id}/recommendation").status_code == 404

    with session_factory() as db:
        assert db.query(Transaction).count() == 1
        assert {event.event_type for event in db.execute(select(OutboxEvent)).scalars()} == {"BANCS", "IA"}


def test_same_idempotency_key_does_not_transfer_twice(api_environment):
    client, session_factory = api_environment
    headers = {"Idempotency-Key": "same-request"}
    first = client.post("/transactions", json=TRANSFER, headers=headers)
    second = client.post("/transactions", json=TRANSFER, headers=headers)
    assert second.status_code == 200
    assert second.json()["transaction_id"] == first.json()["transaction_id"]
    changed = client.post("/transactions", json={**TRANSFER, "amount": "10.00"}, headers=headers)
    assert changed.status_code == 409
    with session_factory() as db:
        assert db.query(Transaction).count() == 1
    assert Decimal(str(client.get("/accounts").json()[0]["balance"])) == Decimal("874.50")


def test_rejected_transfer_does_not_change_balances(api_environment):
    client, session_factory = api_environment
    cases = [
        ({**TRANSFER, "destination_account": "CUEN_001"}, 400),
        ({**TRANSFER, "amount": "9999.00"}, 400),
        ({**TRANSFER, "amount": "1.001"}, 400),
        ({**TRANSFER, "source_account": "UNKNOWN"}, 404),
    ]
    for index, (payload, expected) in enumerate(cases):
        response = client.post("/transactions", json=payload, headers={"Idempotency-Key": f"bad-{index}"})
        assert response.status_code == expected
    with session_factory() as db:
        assert db.query(Transaction).count() == 0
    assert Decimal(str(client.get("/accounts").json()[0]["balance"])) == Decimal("1000.00")


def test_missing_resources_return_404(api_environment):
    client, _ = api_environment
    assert client.get("/transactions/999").status_code == 404
    assert client.get("/etl/runs/999").status_code == 404
