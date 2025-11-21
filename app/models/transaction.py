"""
Transaction database model.
Represents transfers between accounts.
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class TransactionStatus(enum.Enum):
    """Transaction status states."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Transaction(Base):
    """
    Transaction table - stores transfer records.
    """
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(100), unique=True, index=True, nullable=False)
    from_account_id = Column(String(50), ForeignKey("accounts.account_id"), nullable=False)
    to_account_id = Column(String(50), ForeignKey("accounts.account_id"), nullable=False)
    amount = Column(Numeric(precision=15, scale=2), nullable=False)
    status = Column(SQLEnum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    from_account = relationship(
        "Account",
        foreign_keys=[from_account_id],
        back_populates="sent_transactions"
    )
    to_account = relationship(
        "Account",
        foreign_keys=[to_account_id],
        back_populates="received_transactions"
    )
    
    def __repr__(self):
        return f"<Transaction(id={self.transaction_id}, from={self.from_account_id}, to={self.to_account_id}, amount={self.amount})>"