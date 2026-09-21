import logging
import time
from decimal import Decimal

from fastapi import HTTPException
from prometheus_client import Histogram
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Account, OutboxEvent, Transaction
from .schemas import TransactionCreate

logger = logging.getLogger("transaction_service")
LOCK_WAIT = Histogram("smartbancs_account_lock_wait_seconds", "Tiempo que tardó en obtener los bloqueos de las filas de la cuenta")


def process_transaction(db: Session, payload: TransactionCreate, idempotency_key: str) -> Transaction:
    existing = db.execute(
        select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        .execution_options(query_name="transaction_by_idempotency_key")
    ).scalar_one_or_none()
    if existing:
        if not same_request(db, existing, payload):
            raise HTTPException(status_code=409, detail="La clave de idempotencia ya está asociada a otra transferencia.")
        return existing

    if payload.source_account == payload.destination_account:
        raise HTTPException(status_code=400, detail="La cuenta de origen y la cuenta de destino deben ser diferentes.")

    started = time.perf_counter()
    accounts = db.execute(
        select(Account)
        .where(Account.account_number.in_(sorted([payload.source_account, payload.destination_account])))
        .order_by(Account.account_number)
        .with_for_update()
        .execution_options(query_name="lock_transfer_accounts")
    ).scalars().all()
    wait_seconds = time.perf_counter() - started
    LOCK_WAIT.observe(wait_seconds)
    logger.info(f"Cuentas_bloqueadas Tiempo_espera_bloqueo_ms={wait_seconds * 1000:.2f}")
    by_number = {account.account_number: account for account in accounts}
    source = by_number.get(payload.source_account)
    destination = by_number.get(payload.destination_account)
    if source is None or destination is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")
    currency = payload.currency.upper()
    if source.currency != currency or destination.currency != currency:
        raise HTTPException(status_code=400, detail="Diferencia en tipo de moneda")
    amount = Decimal(payload.amount)
    if amount.as_tuple().exponent < -2:
        raise HTTPException(status_code=400, detail="El monto tiene más de dos decimales.")
    if source.balance < amount:
        raise HTTPException(status_code=400, detail="Fondos insuficientes.")

    source.balance -= amount
    destination.balance += amount
    transaction = Transaction(
        source_account_id=source.id,
        destination_account_id=destination.id,
        amount=amount,
        currency=currency,
        status="COMPLETADA",
        idempotency_key=idempotency_key,
    )
    db.add(transaction)
    db.flush()
    db.add_all([
        OutboxEvent(transaction_id=transaction.id, event_type="BANCS"),
        OutboxEvent(transaction_id=transaction.id, event_type="IA"),
    ])
    return transaction


def same_request(db: Session, transaction: Transaction, payload: TransactionCreate) -> bool:
    source = db.get(Account, transaction.source_account_id)
    destination = db.get(Account, transaction.destination_account_id)
    return (
        source.account_number == payload.source_account
        and destination.account_number == payload.destination_account
        and transaction.amount == payload.amount
        and transaction.currency == payload.currency.upper()
    )
