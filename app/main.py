import logging
import time
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.transform import run_etl

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError as PoolTimeoutError
from sqlalchemy.orm import Session

from .database import get_db
from .logs_config import configure_logging, request_id_context
from .models import Account, EtlRun, OutboxEvent, Recommendation, Transaction
from .schemas import TransactionCreate, TransactionDetail, TransactionResponse
from .services import process_transaction, same_request

configure_logging()
logger = logging.getLogger("transaction_service")

REQUESTS = Counter("smartbancs_http_requests_total", "HTTP requests", ["endpoint", "status"])
TRANSACTION_DURATION = Histogram("smartbancs_transaction_duration_seconds", "Tiempo de respuesta de la transferencia")
DB_ERRORS = Counter("smartbancs_db_errors_total", "DB fallos", ["kind"])

app = FastAPI(title="SmartBancs Transaction Service", version="0.2.0")


@app.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.execute(select(Account).order_by(Account.account_number)).scalars().all()
    return [
        {"account_number": account.account_number, "currency": account.currency, "balance": account.balance}
        for account in accounts
    ]


@app.post("/etl/run")
def execute_sample_etl(db: Session = Depends(get_db)):
    with TemporaryDirectory() as directory:
        output_dir = Path(directory)
        summary = run_etl(output_dir=output_dir)

        def read_rows(filename: str):
            with (output_dir / filename).open(newline="", encoding="utf-8") as file:
                return list(csv.DictReader(file))

        run = EtlRun(summary=summary, valid_rows=read_rows("clean_transactions.csv"),
                     rejected_rows=read_rows("rejected_transactions.csv"), status="PENDIENTE")
    db.add(run)
    db.commit()
    db.refresh(run)
    return etl_run_response(run)


def etl_run_response(run: EtlRun):
    return {"run_id": run.id, "summary": run.summary, "valid": run.valid_rows,
            "rejected": run.rejected_rows, "recommendation_status": run.status,
            "recommendation": run.recommendation, "model_version": run.model_version,
            "recommendation_error": run.last_error if run.status == "FALLIDO" else None}


@app.get("/etl/runs/{run_id}")
def get_etl_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(EtlRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Ejecución ETL no encontrada.")
    return etl_run_response(run)


def event_status(db: Session, transaction_id: int, event_type: str) -> str:
    return db.execute(
        select(OutboxEvent.status).where(
            OutboxEvent.transaction_id == transaction_id,
            OutboxEvent.event_type == event_type,
        ).execution_options(query_name="outbox_event_status")
    ).scalar_one()


def sync_status(db: Session, transaction_id: int) -> str:
    return event_status(db, transaction_id, "BANCS")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1).execution_options(query_name="health_query"))
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)


@app.post("/transactions", response_model=TransactionResponse)
def create_transaction(payload: TransactionCreate,db: Session = Depends(get_db),idempotency_key: str = Header(min_length=1, max_length=100)):
    started = time.perf_counter()
    token = request_id_context.set(idempotency_key)
    status = "500"
    try:
        transaction = process_transaction(db, payload, idempotency_key)
        db.commit()
        logger.info(f"Transacion_bb_commit id_transaccion= {transaction.id}")
        logger.info(f"Transaction_completa id_transaccion= {transaction.id} Estado= {transaction.status}")
        result = TransactionResponse(
            transaction_id=transaction.id,
            status=transaction.status,
            bancs_reference=transaction.bancs_reference,
            bancs_sync_status=sync_status(db, transaction.id),
        )
        status = "200"
        return result
    except IntegrityError:
        db.rollback()
        existing = db.execute(select(Transaction).where(Transaction.idempotency_key == idempotency_key)).scalar_one_or_none()
        if existing and same_request(db, existing, payload):
            result = TransactionResponse(
                transaction_id=existing.id, status=existing.status,
                bancs_reference=existing.bancs_reference,
                bancs_sync_status=sync_status(db, existing.id),
            )
            status = "200"
            return result
        status = "409"
        raise HTTPException(status_code=409, detail="Conflicto de llave de idempotencia.")
    except HTTPException as exc:
        db.rollback()
        status = str(exc.status_code)
        logger.warning(f"Transaccion rechazada Estado={status} detalle={exc.detail}")
        raise
    except (OperationalError, PoolTimeoutError) as exc:
        db.rollback()
        code = getattr(getattr(exc, "orig", None), "pgcode", None)
        kind = {"40P01": "deadlock", "55P03": "lock_timeout", "57014": "statement_timeout"}.get(code, "pool_or_db_timeout")
        DB_ERRORS.labels(kind=kind).inc()
        logger.exception("Transaccion fallida en BD Tipo=%s", kind)
        status = "503"
        raise HTTPException(status_code=503, detail="Base de datos no disponible en este momento.")
    except Exception:
        db.rollback()
        logger.exception("transaccion_fallida")
        raise HTTPException(status_code=500, detail="Error Interno en la Transaction.")
    finally:
        REQUESTS.labels(endpoint="/transactions", status=status).inc()
        TRANSACTION_DURATION.observe(time.perf_counter() - started)
        request_id_context.reset(token)


@app.get("/transactions/{transaction_id}", response_model=TransactionDetail)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaccion no encontrada.")
    source = db.get(Account, transaction.source_account_id)
    destination = db.get(Account, transaction.destination_account_id)
    return TransactionDetail(
        transaction_id=transaction.id,
        source_account=source.account_number,
        destination_account=destination.account_number,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        bancs_reference=transaction.bancs_reference,
        bancs_sync_status=sync_status(db, transaction.id),
        recommendation_status=event_status(db, transaction.id, "IA"),
    )


@app.get("/transactions/{transaction_id}/recommendation")
def get_recommendation(transaction_id: int, db: Session = Depends(get_db)):
    recommendation = db.execute(
        select(Recommendation).where(Recommendation.transaction_id == transaction_id)
        .execution_options(query_name="recommendation_by_transaction")
    ).scalar_one_or_none()
    if recommendation is None:
        raise HTTPException(status_code=404, detail="No hay una recomendacion lista o no se encontro la transaccion.")
    return {
        "transaction_id": transaction_id,
        "recommendation": recommendation.message,
        "model_version": recommendation.model_version,
    }
