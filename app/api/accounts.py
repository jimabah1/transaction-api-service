"""
Account API endpoints.
Handles account creation, retrieval, and balance queries.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal

from app.database import get_db
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountResponse, AccountBalance

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    account_data: AccountCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new account.
    
    - **account_id**: Unique identifier for the account
    - **owner_name**: Name of the account owner
    - **initial_balance**: Starting balance (default: 0.00)
    """
    # Check if account already exists
    existing_account = db.query(Account).filter(
        Account.account_id == account_data.account_id
    ).first()
    
    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account {account_data.account_id} already exists"
        )
    
    # Validate initial balance
    if account_data.initial_balance < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Initial balance cannot be negative"
        )
    
    # Create new account
    new_account = Account(
        account_id=account_data.account_id,
        owner_name=account_data.owner_name,
        balance=account_data.initial_balance
    )
    
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    
    return new_account


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: str,
    db: Session = Depends(get_db)
):
    """
    Get account details by account ID.
    """
    account = db.query(Account).filter(Account.account_id == account_id).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )
    
    return account


@router.get("/{account_id}/balance", response_model=AccountBalance)
def get_account_balance(
    account_id: str,
    db: Session = Depends(get_db)
):
    """
    Get account balance.
    """
    account = db.query(Account).filter(Account.account_id == account_id).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )
    
    return AccountBalance(
        account_id=account.account_id,
        balance=account.balance
    )


@router.get("/", response_model=List[AccountResponse])
def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all accounts with pagination.
    
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Maximum number of records to return (default: 100)
    """
    accounts = db.query(Account).offset(skip).limit(limit).all()
    return accounts


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete an account.
    """
    account = db.query(Account).filter(Account.account_id == account_id).first()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )
    
    # Check if account has transactions
    if account.balance != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete account with non-zero balance"
        )
    
    db.delete(account)
    db.commit()
    
    return None