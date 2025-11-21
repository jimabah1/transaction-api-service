"""
Pydantic schemas for Account API requests and responses.
"""

from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
from typing import Optional


class AccountCreate(BaseModel):
    """Schema for creating a new account."""
    account_id: str = Field(..., min_length=1, max_length=50, description="Unique account identifier")
    owner_name: str = Field(..., min_length=1, max_length=100, description="Account owner name")
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0, description="Initial account balance")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "account_id": "ACC001",
                "owner_name": "John Doe",
                "initial_balance": 1000.00
            }
        }
    )


class AccountResponse(BaseModel):
    """Schema for account response."""
    id: int
    account_id: str
    owner_name: str
    balance: Decimal
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AccountBalance(BaseModel):
    """Schema for account balance response."""
    account_id: str
    balance: Decimal
    
    model_config = ConfigDict(from_attributes=True)