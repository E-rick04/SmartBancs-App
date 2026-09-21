from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Account(Base):
    __tablename__ = "cuenta"
    __table_args__ = (CheckConstraint("saldo >= 0", name="ck_cuentas_saldo_no_negativo"),UniqueConstraint("numero_cuenta", name="uq_cuentas_numero_cuenta"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_number: Mapped[str] = mapped_column("numero_cuenta", String(30), unique=True, index=True)
    currency: Mapped[str] = mapped_column("moneda", String(3), default="USD")
    balance: Mapped[Decimal] = mapped_column("saldo", Numeric(18, 2), default=0)


class Transaction(Base):
    __tablename__ = "transaccion"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_transacciones_monto_positivo"),
        CheckConstraint("id_cuenta_origen <> id_cuenta_destino",name="ck_transacciones_cuentas_distintas"),
        UniqueConstraint("clave_idempotencia",name="uq_transacciones_clave_idempotencia"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_account_id: Mapped[int] = mapped_column("id_cuenta_origen", ForeignKey("cuenta.id"))
    destination_account_id: Mapped[int] = mapped_column("id_cuenta_destino", ForeignKey("cuenta.id"))
    amount: Mapped[Decimal] = mapped_column("monto" ,Numeric(18, 2))
    currency: Mapped[str] = mapped_column("moneda", String(3))
    status: Mapped[str] = mapped_column("estado", String(20), default="COMPLETADA")
    bancs_reference: Mapped[str | None] = mapped_column("referencia_bancs", String(50), nullable=True)
    idempotency_key: Mapped[str] = mapped_column("clave_idempotencia", String(100))
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, default=datetime.utcnow)


class Recommendation(Base):
    __tablename__ = "recomendacion"
    __table_args__ = (UniqueConstraint("id_transaccion", name="uq_recomendaciones_transaccion"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column("id_transaccion", ForeignKey("transaccion.id"))
    message: Mapped[str] = mapped_column("mensaje", Text)
    model_version: Mapped[str] = mapped_column("version_modelo",String(50))
    created_at: Mapped[datetime] = mapped_column("creado_en", DateTime, default=datetime.utcnow)


class OutboxEvent(Base):
    __tablename__ = "evento_salida"
    __table_args__ = (UniqueConstraint("id_transaccion", "tipo_evento",name="uq_eventos_salida_transaccion_tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column("id_transaccion",ForeignKey("transaccion.id"))
    event_type: Mapped[str] = mapped_column("tipo_evento" , String(20))
    status: Mapped[str] = mapped_column("estado", String(20), default="PENDIENTE")
    attempts: Mapped[int] = mapped_column("intentos", default=0)
    available_at: Mapped[datetime] = mapped_column("disponible_en", DateTime, default=datetime.utcnow)
    locked_at: Mapped[datetime | None] = mapped_column("bloqueado_en" ,DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column("ultimo_error", String(255), nullable=True)


class EtlRun(Base):
    __tablename__ = "etl_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    summary: Mapped[dict] = mapped_column(JSON)
    valid_rows: Mapped[list] = mapped_column(JSON)
    rejected_rows: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="PENDIENTE")
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
