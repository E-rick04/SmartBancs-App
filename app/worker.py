import logging
import os
import time
from datetime import datetime, timedelta

import requests
from sqlalchemy import func, or_, select

from .database import SessionLocal
from .logs_config import configure_logging, request_id_context
from .models import EtlRun, OutboxEvent, Recommendation, Transaction

configure_logging()
logger = logging.getLogger("outbox_worker")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8001")
POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "0.2"))
EVENT_TYPE = os.getenv("EVENT_TYPE")


def recommendation_payload(db, transaction: Transaction) -> dict:
    """Use only earlier transfers so retries produce the same context."""
    recent_count, recent_total = db.execute(
        select(func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.source_account_id == transaction.source_account_id,
            Transaction.currency == transaction.currency,
            Transaction.status == "COMPLETADA",
            Transaction.created_at >= transaction.created_at - timedelta(hours=24),
            Transaction.created_at <= transaction.created_at,
            Transaction.id < transaction.id,
        )
        .execution_options(query_name="recent_source_transfers_for_recommendation")
    ).one()
    return {
        "transaction_id": transaction.id,
        "amount": str(transaction.amount),
        "currency": transaction.currency,
        "recent_count_24h": recent_count,
        "recent_total_24h": str(recent_total),
    }


def claim_event():
    with SessionLocal.begin() as db:
        now = datetime.utcnow()
        statement = select(OutboxEvent)
        if EVENT_TYPE:
            statement = statement.where(OutboxEvent.event_type == EVENT_TYPE)
        event = db.execute(
            statement
            .where(
                or_(
                    (OutboxEvent.status == "PENDIENTE") & (OutboxEvent.available_at <= now),
                    (OutboxEvent.status == "PROCESSING") & (OutboxEvent.locked_at < now - timedelta(seconds=30)),
                )
            )
            .order_by(OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(1)
            .execution_options(query_name="claim_outbox_event")
        ).scalar_one_or_none()
        if event is None:
            return None
        event.status = "PROCESSING"
        event.locked_at = now
        event.attempts += 1
        return event.id, event.transaction_id, event.event_type, event.attempts


def process_event(claimed):
    event_id, transaction_id, event_type, attempts = claimed
    token = request_id_context.set(str(transaction_id))
    try:
        if event_type == "BANCS":
            # Stable reference makes replay safe for this mock adapter.
            time.sleep(0.05)
            reference = f"BANCS-{transaction_id:06d}"
            with SessionLocal.begin() as db:
                transaction = db.get(Transaction, transaction_id)
                transaction.bancs_reference = reference
                db.get(OutboxEvent, event_id).status = "COMPLETADO"
        elif event_type == "IA":
            with SessionLocal() as db:
                transaction = db.get(Transaction, transaction_id)
                payload = recommendation_payload(db, transaction)
            response = requests.post(
                f"{AI_SERVICE_URL}/recommend",
                json=payload,
                timeout=3,
            )
            response.raise_for_status()
            result = response.json()
            message = result["recommendation"]
            model_version = result["model_version"]
            with SessionLocal.begin() as db:
                recommendation = db.execute(
                    select(Recommendation).where(Recommendation.transaction_id == transaction_id)
                ).scalar_one_or_none()
                if recommendation is None:
                    db.add(Recommendation(transaction_id=transaction_id, message=message, model_version=model_version))
                elif recommendation.model_version != model_version:
                    recommendation.message = message
                    recommendation.model_version = model_version
                db.get(OutboxEvent, event_id).status = "COMPLETADO"
        else:
            raise ValueError(f"Tipo_evento_desconocido: {event_type}")
        logger.info(f"Evento_completado tipo_evento= {event_type} id_transaction= {transaction_id}")
    except Exception as exc:
        logger.exception(f"fallo?evento tipo?evento= {event_type} id_transaccion={transaction_id} intentos= {attempts}")
        with SessionLocal.begin() as db:
            event = db.get(OutboxEvent, event_id)
            event.status = "FALLIDO" if attempts >= 5 else "PENDIENTE"
            event.available_at = datetime.utcnow() + timedelta(seconds=min(2 ** attempts, 60))
            event.last_error = str(exc)[:255]
    finally:
        request_id_context.reset(token)


def claim_etl_run():
    with SessionLocal.begin() as db:
        now = datetime.utcnow()
        run = db.execute(
            select(EtlRun).where(or_(
                (EtlRun.status == "PENDIENTE") & (EtlRun.available_at <= now),
                (EtlRun.status == "PROCESSING") & (EtlRun.locked_at < now - timedelta(seconds=30)),
            )).order_by(EtlRun.id).with_for_update(skip_locked=True).limit(1)
        ).scalar_one_or_none()
        if run is None:
            return None
        run.status = "PROCESSING"
        run.locked_at = now
        run.attempts += 1
        return run.id, run.attempts


def process_etl_run(claimed):
    run_id, attempts = claimed
    try:
        with SessionLocal() as db:
            summary = db.get(EtlRun, run_id).summary
        response = requests.post(
            f"{AI_SERVICE_URL}/recommend/etl",
            json={"run_id": run_id, **summary}, timeout=5,
        )
        response.raise_for_status()
        result = response.json()
        with SessionLocal.begin() as db:
            run = db.get(EtlRun, run_id)
            run.recommendation = result["recommendation"]
            run.model_version = result["model_version"]
            run.status = "COMPLETADO"
            run.last_error = None
        logger.info("Recomendación ETL completada run_id=%s", run_id)
    except Exception as exc:
        logger.exception("Recomendación ETL fallida run_id=%s", run_id)
        with SessionLocal.begin() as db:
            run = db.get(EtlRun, run_id)
            run.status = "FALLIDO" if attempts >= 5 else "PENDIENTE"
            run.available_at = datetime.utcnow() + timedelta(seconds=min(2 ** attempts, 60))
            run.last_error = str(exc)[:255]


def main():
    while True:
        try:
            claimed = claim_event()
            if claimed:
                process_event(claimed)
            elif EVENT_TYPE == "IA":
                etl_run = claim_etl_run()
                if etl_run:
                    process_etl_run(etl_run)
                else:
                    time.sleep(POLL_SECONDS)
            else:
                time.sleep(POLL_SECONDS)
        except Exception:
            logger.exception("fallo_ejecucion_worker")
            time.sleep(1)


if __name__ == "__main__":
    main()
