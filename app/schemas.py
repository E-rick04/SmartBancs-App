from decimal import Decimal

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    source_account: str
    destination_account: str
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class TransactionResponse(BaseModel):
    transaction_id: int
    status: str
    bancs_reference: str | None = None
    bancs_sync_status: str


class TransactionDetail(BaseModel):
    transaction_id: int
    source_account: str
    destination_account: str
    amount: Decimal
    currency: str
    status: str
    bancs_reference: str | None = None
    bancs_sync_status: str
    recommendation_status: str
