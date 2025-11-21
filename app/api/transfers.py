"""
Transfer API endpoints.
Handles money transfers between accounts.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
import uuid

from app.database import get_db
from app.models.account import Account
from app.models.transaction import Transaction, TransactionStatus
from app.schemas.transaction import TransferRequest, TransactionResponse

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    transfer_data: TransferRequest,
    db: Session = Depends(get_db)
):
    """
    Process a transfer between two accounts.
    
    Implements:
    - Atomicity: Transaction completes fully or fails completely
    - Idempotency: Duplicate transaction_id rejected
    - Double-entry bookkeeping: Debit from source, credit to destination
    - Concurrency: Row-level locking to prevent race conditions
    
    - **from_account_id**: Source account
    - **to_account_id**: Destination account  
    - **amount**: Transfer amount (must be positive)
    - **description**: Optional transfer description
    - **transaction_id**: Optional custom ID for idempotency
    """
    
    # Validate accounts are different
    if transfer_data.from_account_id == transfer_data.to_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer to the same account"
        )
    
    # Generate transaction ID if not provided
    transaction_id = transfer_data.transaction_id or str(uuid.uuid4())
    
    # Check for duplicate transaction ID (idempotency)
    existing_transaction = db.query(Transaction).filter(
        Transaction.transaction_id == transaction_id
    ).first()
    
    if existing_transaction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction {transaction_id} already exists"
        )
    
    try:
        # Start explicit transaction with row-level locking
        # Lock accounts in consistent order to prevent deadlocks
        account_ids = sorted([transfer_data.from_account_id, transfer_data.to_account_id])
        
        # Get accounts with row-level locks (SELECT FOR UPDATE)
        # This prevents other transactions from modifying these rows
        locked_accounts = {}
        for account_id in account_ids:
            account = db.query(Account).filter(
                Account.account_id == account_id
            ).with_for_update().first()
            
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Account {account_id} not found"
                )
            locked_accounts[account_id] = account
        
        from_account = locked_accounts[transfer_data.from_account_id]
        to_account = locked_accounts[transfer_data.to_account_id]
        
        # Check sufficient funds
        if from_account.balance < transfer_data.amount:
            # Create failed transaction record
            failed_transaction = Transaction(
                transaction_id=transaction_id,
                from_account_id=transfer_data.from_account_id,
                to_account_id=transfer_data.to_account_id,
                amount=transfer_data.amount,
                status=TransactionStatus.FAILED,
                description=transfer_data.description
            )
            db.add(failed_transaction)
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient funds. Balance: {from_account.balance}, Required: {transfer_data.amount}"
            )
        
        # Create transaction record
        transaction = Transaction(
            transaction_id=transaction_id,
            from_account_id=transfer_data.from_account_id,
            to_account_id=transfer_data.to_account_id,
            amount=transfer_data.amount,
            status=TransactionStatus.PENDING,
            description=transfer_data.description
        )
        
        # Execute transfer (atomic operation within database transaction)
        from_account.balance -= transfer_data.amount
        to_account.balance += transfer_data.amount
        
        # Mark transaction as completed
        transaction.status = TransactionStatus.COMPLETED
        
        # Save all changes atomically
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return transaction
        
    except HTTPException:
        # Re-raise HTTP exceptions (expected errors)
        db.rollback()
        raise
    except Exception as e:
        # Rollback on unexpected errors
        db.rollback()
        
        # Try to create failed transaction record
        try:
            failed_transaction = Transaction(
                transaction_id=transaction_id,
                from_account_id=transfer_data.from_account_id,
                to_account_id=transfer_data.to_account_id,
                amount=transfer_data.amount,
                status=TransactionStatus.FAILED,
                description=transfer_data.description
            )
            db.add(failed_transaction)
            db.commit()
        except:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer failed: {str(e)}"
        )

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transfer(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Get transfer details by transaction ID.
    """
    transaction = db.query(Transaction).filter(
        Transaction.transaction_id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found"
        )
    
    return transaction


@router.get("/account/{account_id}", response_model=List[TransactionResponse])
def get_account_transfers(
    account_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all transfers for a specific account (sent and received).
    
    - **account_id**: Account to query
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Maximum number of records to return (default: 100)
    """
    # Check if account exists
    account = db.query(Account).filter(Account.account_id == account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )
    
    # Get transactions where account is sender or receiver
    transactions = db.query(Transaction).filter(
        (Transaction.from_account_id == account_id) | 
        (Transaction.to_account_id == account_id)
    ).order_by(Transaction.created_at.desc()).offset(skip).limit(limit).all()
    
    return transactions


@router.get("/", response_model=List[TransactionResponse])
def list_transfers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all transfers with pagination.
    
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Maximum number of records to return (default: 100)
    """
    transactions = db.query(Transaction).order_by(
        Transaction.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return transactions