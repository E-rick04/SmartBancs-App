import time
import logging
from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="SmartBancs AI Mock Service")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_service")


class RecommendationRequest(BaseModel):
    transaction_id: int
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    recent_count_24h: int = Field(default=0, ge=0)
    recent_total_24h: Decimal = Field(default=Decimal("0"), ge=0)


class EtlRecommendationRequest(BaseModel):
    run_id: int
    input_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    issues: dict[str, int]


ETL_ACTIONS = (
    (
        "missing_transaction_id",
        "asigna un ID a las filas sin identificador",
    ),
    (
        "missing_or_invalid_amount",
        "completa los montos faltantes o no numéricos",
    ),
    (
        "non_positive_amount",
        "corrige los montos iguales o menores que cero",
    ),
    (
        "invalid_date",
        "corrige las fechas inválidas",
    ),
    (
        "invalid_currency",
        "normaliza las monedas a códigos de tres letras",
    ),
    (
        "duplicate_transaction_id",
        "revisa los ID duplicados y conserva solo el registro correcto",
    ),
)


@app.post("/recommend/etl")
def recommend_etl(payload: EtlRecommendationRequest):
    actions = [
        action
        for key, action in ETL_ACTIONS
        if payload.issues.get(key, 0) > 0
    ]

    if actions:
        message = (
            f"Corrige los {payload.rejected_rows} registros rechazados: "
            + "; ".join(actions)
            + ". Vuelve a ejecutar el ETL y confirma que no queden "
              "rechazos antes de importar los datos."
        )
    else:
        message = (
            f"Los {payload.valid_rows} registros pasaron la validación. "
            "Revisa una muestra contra el archivo original y autoriza "
            "la importación si coincide."
        )

    return {
        "run_id": payload.run_id,
        "recommendation": message,
        "model_version": "etl-rules-v1",
    }


def build_recommendation(
    payload: RecommendationRequest,
) -> tuple[str, str, list[str]]:
    amount = payload.amount
    currency = payload.currency
    transfer_count = payload.recent_count_24h + 1
    total_24h = payload.recent_total_24h + amount

    reasons: list[str] = []

    if amount < Decimal("100"):
        reasons.append(
            f"la transferencia es menor a 100 {currency}"
        )

        message = (
            f"Registra la transferencia de {amount:.2f} {currency} "
            "como parte de tus gastos habituales. Mantener un registro "
            "de movimientos pequeños puede ayudarte a identificar "
            "en qué categorías estás gastando más."
        )

        level = "LOW"

    elif amount < Decimal("500"):
        reasons.append(
            f"la transferencia está entre 100 y 500 {currency}"
        )

        message = (
            f"Revisa cómo afecta la transferencia de {amount:.2f} {currency} "
            "a tu presupuesto del mes. Si este tipo de movimiento es "
            "frecuente, considera establecer un límite de gasto para "
            "mantener tus objetivos financieros."
        )

        level = "MEDIUM"

    else:
        reasons.append(
            f"la transferencia alcanza o supera 500 {currency}"
        )

        message = (
            f"Considera revisar el impacto de la transferencia de "
            f"{amount:.2f} {currency} en tus ahorros y presupuesto. "
            "Si cuentas con un fondo de emergencia, verifica que "
            "continúe cubriendo tus gastos previstos."
        )

        level = "MEDIUM"


    if transfer_count >= 3:
        reasons.append(
            f"se registraron {transfer_count} transferencias en 24 horas"
        )

        message += (
            f" Además, se registraron {transfer_count} transferencias "
            "en las últimas 24 horas; revisar el patrón de movimientos "
            "puede ayudarte a controlar mejor tus gastos."
        )

        level = "MEDIUM"

    if total_24h >= Decimal("1000"):
        reasons.append(
            f"el total transferido en 24 horas alcanza "
            f"{total_24h:.2f} {currency}"
        )

        message += (
            f" El total de movimientos en las últimas 24 horas alcanza "
            f"{total_24h:.2f} {currency}. Considera revisar tu flujo "
            "de dinero y confirmar que esté alineado con tu presupuesto."
        )

        level = "HIGH"

    elif total_24h >= Decimal("750"):
        reasons.append(
            f"el total transferido en 24 horas alcanza "
            f"{total_24h:.2f} {currency}"
        )

        message += (
            f" El acumulado de movimientos en 24 horas es de "
            f"{total_24h:.2f} {currency}; revisar tus gastos recientes "
            "puede ayudarte a mantener el presupuesto bajo control."
        )

    if amount >= Decimal("1000"):
        reasons.append(
            f"la transferencia individual alcanza 1000 {currency}"
        )

        message = (
            f"La transferencia de {amount:.2f} {currency} representa "
            "un movimiento importante. Considera revisar tu presupuesto "
            "y verificar que esta operación no reduzca el dinero "
            "destinado a tus gastos esenciales o a tu fondo de emergencia."
        )

        level = "HIGH"

    return level, message, reasons


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recommend")
def recommend(payload: RecommendationRequest):
    time.sleep(1) #Simula proceso de razonamiento

    level, message, reasons = build_recommendation(payload)

    logger.info(
        "recomendacion_entregada "
        f"id_transaccion={payload.transaction_id} "
        f"level={level}"
    )

    return {
        "transaction_id": payload.transaction_id,
        "recommendation": message,
        "attention_level": level,
        "reasons": reasons,
        "model_version": "IA Mock Model",
    }