import logging
import os
import time

from prometheus_client import Counter, Histogram
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


# Compose provides this variable when the app runs in Docker.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://smartbancs:smartbancs@localhost:5432/smartbancs",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=2,
    connect_args={
        "options": "-c statement_timeout=1500 -c lock_timeout=1000"
    },
)

logger = logging.getLogger("database")

DB_QUERY_DURATION = Histogram("smartbancs_db_query_duration_seconds","Tiempo empleado en ejecutar consultas a la base de datos",["query_name"])

DB_QUERY_ERRORS = Counter("smartbancs_db_query_errors_total","Número de errores en consultas a la base de datos",["query_name"])


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    # Guarda lahora de inicio para calcular la duracion de la solicitud.
    context.query_start_time = time.perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    query_name = context.execution_options.get("query_name","other_query")

    duration = time.perf_counter() - context.query_start_time
    DB_QUERY_DURATION.labels(query_name=query_name).observe(duration)

    if duration >= 0.1:
        logger.warning(f"Solicitud lenta: nombre={query_name} duracion ms={duration * 1000:.2f}")


@event.listens_for(engine, "handle_error")
def handle_error(context):
    query_name = "conn"

    if context.execution_context is not None:
        query_name = context.execution_context.execution_options.get("query_name","other_query")

    DB_QUERY_ERRORS.labels(query_name=query_name).inc()

    error_code = getattr(context.original_exception, "pgcode", None)
    logger.error(f"Error en base de datos: query={query_name} postgres_codigo={error_code}")


# Creanueva conn a base de datos.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()