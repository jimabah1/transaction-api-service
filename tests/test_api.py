"""
API tests for Transaction API Service.
Tests account creation, transfers, and error handling.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

# Use PostgreSQL test database
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/transaction_api_test"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ==================== HEALTH CHECK TESTS ====================

def test_root_endpoint():
    """Test root endpoint returns correct response."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert "Transaction API Service" in data["message"]


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ==================== ACCOUNT TESTS ====================

def test_create_account():
    """Test creating a new account."""
    response = client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Test User",
            "initial_balance": 1000.00
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["account_id"] == "TEST001"
    assert data["owner_name"] == "Test User"
    assert float(data["balance"]) == 1000.00


def test_create_duplicate_account():
    """Test that creating duplicate account fails."""
    # Create first account
    client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Test User",
            "initial_balance": 1000.00
        }
    )
    
    # Try to create duplicate
    response = client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Another User",
            "initial_balance": 500.00
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_account_negative_balance():
    """Test that negative initial balance is rejected."""
    response = client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Test User",
            "initial_balance": -100.00
        }
    )
    assert response.status_code == 422


def test_get_account():
    """Test retrieving account details."""
    # Create account
    client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Test User",
            "initial_balance": 1000.00
        }
    )
    
    # Get account
    response = client.get("/api/v1/accounts/TEST001")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "TEST001"
    assert float(data["balance"]) == 1000.00


def test_get_nonexistent_account():
    """Test that getting non-existent account returns 404."""
    response = client.get("/api/v1/accounts/NONEXISTENT")
    assert response.status_code == 404


def test_get_account_balance():
    """Test getting account balance."""
    # Create account
    client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Test User",
            "initial_balance": 1000.00
        }
    )
    
    # Get balance
    response = client.get("/api/v1/accounts/TEST001/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == "TEST001"
    assert float(data["balance"]) == 1000.00


def test_list_accounts():
    """Test listing accounts."""
    # Create multiple accounts
    for i in range(3):
        client.post(
            "/api/v1/accounts/",
            json={
                "account_id": f"TEST{i:03d}",
                "owner_name": f"User {i}",
                "initial_balance": 1000.00
            }
        )
    
    # List accounts
    response = client.get("/api/v1/accounts/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_delete_account():
    """Test deleting an account with zero balance."""
    # Create account with zero balance
    client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Test User",
            "initial_balance": 0.00
        }
    )
    
    # Delete account
    response = client.delete("/api/v1/accounts/TEST001")
    assert response.status_code == 204
    
    # Verify account is gone
    response = client.get("/api/v1/accounts/TEST001")
    assert response.status_code == 404


def test_delete_account_with_balance():
    """Test that deleting account with balance fails."""
    # Create account with balance
    client.post(
        "/api/v1/accounts/",
        json={
            "account_id": "TEST001",
            "owner_name": "Test User",
            "initial_balance": 1000.00
        }
    )
    
    # Try to delete
    response = client.delete("/api/v1/accounts/TEST001")
    assert response.status_code == 400
    assert "non-zero balance" in response.json()["detail"]


# ==================== TRANSFER TESTS ====================

def test_create_transfer():
    """Test successful transfer between accounts."""
    # Create two accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST002", "owner_name": "Bob", "initial_balance": 500.00}
    )
    
    # Make transfer
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "TEST001",
            "to_account_id": "TEST002",
            "amount": 250.00,
            "description": "Test transfer"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert float(data["amount"]) == 250.00
    assert data["status"] == "completed"
    assert data["from_account_id"] == "TEST001"
    assert data["to_account_id"] == "TEST002"
    
    # Verify balances
    balance1 = client.get("/api/v1/accounts/TEST001/balance").json()
    balance2 = client.get("/api/v1/accounts/TEST002/balance").json()
    assert float(balance1["balance"]) == 750.00
    assert float(balance2["balance"]) == 750.00


def test_transfer_insufficient_funds():
    """Test transfer with insufficient funds fails."""
    # Create two accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 100.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST002", "owner_name": "Bob", "initial_balance": 500.00}
    )
    
    # Try transfer with insufficient funds
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "TEST001",
            "to_account_id": "TEST002",
            "amount": 200.00
        }
    )
    
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]


def test_transfer_to_same_account():
    """Test that transfer to same account fails."""
    # Create account
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    
    # Try transfer to same account
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "TEST001",
            "to_account_id": "TEST001",
            "amount": 100.00
        }
    )
    
    assert response.status_code == 400
    assert "same account" in response.json()["detail"]


def test_transfer_to_nonexistent_account():
    """Test transfer to non-existent account fails."""
    # Create one account
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    
    # Try transfer to non-existent account
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "TEST001",
            "to_account_id": "NONEXISTENT",
            "amount": 100.00
        }
    )
    
    assert response.status_code == 404


def test_transfer_idempotency():
    """Test that duplicate transaction ID is rejected."""
    # Create two accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST002", "owner_name": "Bob", "initial_balance": 500.00}
    )
    
    # First transfer
    response1 = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "TEST001",
            "to_account_id": "TEST002",
            "amount": 100.00,
            "transaction_id": "IDEMPOTENT_TEST_001"
        }
    )
    assert response1.status_code == 201
    
    # Duplicate transfer (same transaction_id)
    response2 = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "TEST001",
            "to_account_id": "TEST002",
            "amount": 100.00,
            "transaction_id": "IDEMPOTENT_TEST_001"
        }
    )
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]
    
    # Verify only one transfer occurred
    balance1 = client.get("/api/v1/accounts/TEST001/balance").json()
    assert float(balance1["balance"]) == 900.00  # Only one debit


def test_get_transfer():
    """Test retrieving transfer details."""
    # Create accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST002", "owner_name": "Bob", "initial_balance": 500.00}
    )
    
    # Make transfer
    transfer_response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "TEST001",
            "to_account_id": "TEST002",
            "amount": 250.00
        }
    )
    transaction_id = transfer_response.json()["transaction_id"]
    
    # Get transfer
    response = client.get(f"/api/v1/transfers/{transaction_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["transaction_id"] == transaction_id
    assert float(data["amount"]) == 250.00


def test_get_account_transfers():
    """Test getting all transfers for an account."""
    # Create accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST002", "owner_name": "Bob", "initial_balance": 500.00}
    )
    
    # Make multiple transfers
    client.post(
        "/api/v1/transfers/",
        json={"from_account_id": "TEST001", "to_account_id": "TEST002", "amount": 100.00}
    )
    client.post(
        "/api/v1/transfers/",
        json={"from_account_id": "TEST001", "to_account_id": "TEST002", "amount": 50.00}
    )
    
    # Get transfers for TEST001
    response = client.get("/api/v1/transfers/account/TEST001")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_transfers():
    """Test listing all transfers."""
    # Create accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST001", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "TEST002", "owner_name": "Bob", "initial_balance": 500.00}
    )
    
    # Make transfers
    for i in range(3):
        client.post(
            "/api/v1/transfers/",
            json={"from_account_id": "TEST001", "to_account_id": "TEST002", "amount": 50.00}
        )
    
    # List transfers
    response = client.get("/api/v1/transfers/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3