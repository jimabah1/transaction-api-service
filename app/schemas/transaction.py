"""
Pydantic schemas for Transaction API requests and responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import Optional
from app.models.transaction import TransactionStatus


class TransferRequest(BaseModel):
    """Schema for initiating a transfer."""
    from_account_id: str = Field(..., min_length=1, max_length=50, description="Source account ID")
    to_account_id: str = Field(..., min_length=1, max_length=50, description="Destination account ID")
    amount: Decimal = Field(..., gt=0, description="Transfer amount (must be positive)")
    description: Optional[str] = Field(None, max_length=500, description="Optional transfer description")
    transaction_id: Optional[str] = Field(None, max_length=100, description="Optional custom transaction ID for idempotency")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "from_account_id": "ACC001",
                "to_account_id": "ACC002",
                "amount": 250.00,
                "description": "Payment for services"
            }
        }
    )


class TransactionResponse(BaseModel):
    """Schema for transaction response."""
    id: int
    transaction_id: str
    from_account_id: str
    to_account_id: str
    amount: Decimal
    status: TransactionStatus
    description: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)