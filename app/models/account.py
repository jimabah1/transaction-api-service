"""
Account database model.
Represents bank accounts in the system.
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Account(Base):
    """
    Account table - stores bank account information.
    """
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(50), unique=True, index=True, nullable=False)
    owner_name = Column(String(100), nullable=False)
    balance = Column(Numeric(precision=15, scale=2), nullable=False, default=0.00)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to transactions
    sent_transactions = relationship(
        "Transaction",
        foreign_keys="Transaction.from_account_id",
        back_populates="from_account"
    )
    received_transactions = relationship(
        "Transaction",
        foreign_keys="Transaction.to_account_id",
        back_populates="to_account"
    )
    
    def __repr__(self):
        return f"<Account(account_id={self.account_id}, owner={self.owner_name}, balance={self.balance})>"