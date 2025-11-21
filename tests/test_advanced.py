"""
Advanced tests for Transaction API Service.
Tests concurrency, stress, and edge cases.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from decimal import Decimal

from app.main import app
from app.database import Base, get_db

# Use PostgreSQL test database
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:admin123@localhost:5432/transaction_api_test"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,  # Larger pool for concurrent tests
    max_overflow=40
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables once at module level
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def reset_database():
    """Clear database between tests but don't drop tables."""
    # Delete all records but keep tables
    db = TestingSessionLocal()
    try:
        # Import models
        from app.models.transaction import Transaction
        from app.models.account import Account
        
        # Delete all records
        db.query(Transaction).delete()
        db.query(Account).delete()
        db.commit()
    finally:
        db.close()
    yield


# ==================== CONCURRENCY TESTS ====================

def test_concurrent_account_creation():
    """Test creating multiple accounts concurrently."""
    def create_account(account_num):
        try:
            response = client.post(
                "/api/v1/accounts/",
                json={
                    "account_id": f"CONCURRENT{account_num:03d}",
                    "owner_name": f"User {account_num}",
                    "initial_balance": 1000.00
                }
            )
            return response.status_code == 201
        except Exception:
            return False
    
    # Create 50 accounts concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_account, i) for i in range(50)]
        results = [future.result() for future in as_completed(futures)]
    
    # All should succeed
    assert sum(results) == 50
    
    # Verify all accounts created
    response = client.get("/api/v1/accounts/")
    assert len(response.json()) == 50


def test_concurrent_transfers_same_account():
    """
    Test multiple concurrent transfers from same account.
    Tests race condition handling and atomicity.
    """
    # Create accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "SOURCE", "owner_name": "Source", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    def transfer_money():
        try:
            response = client.post(
                "/api/v1/transfers/",
                json={
                    "from_account_id": "SOURCE",
                    "to_account_id": "DEST",
                    "amount": 10.00
                }
            )
            return response.status_code == 201
        except Exception:
            return False
    
    # Launch 100 concurrent transfers of £10 each (total £1000)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(transfer_money) for _ in range(100)]
        results = [future.result() for future in as_completed(futures)]
    
    # All 100 should succeed (1000 total)
    assert sum(results) == 100
    
    # Verify final balances
    source_balance = client.get("/api/v1/accounts/SOURCE/balance").json()
    dest_balance = client.get("/api/v1/accounts/DEST/balance").json()
    
    assert float(source_balance["balance"]) == 0.00
    assert float(dest_balance["balance"]) == 1000.00


def test_concurrent_transfers_insufficient_funds():
    """
    Test race condition where multiple threads try to spend more than available.
    Only some should succeed, balance should never go negative.
    """
    # Account has £100, try to transfer £20 ten times (total £200)
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "RACER", "owner_name": "Racer", "initial_balance": 100.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "RECEIVER", "owner_name": "Receiver", "initial_balance": 0.00}
    )
    
    def attempt_transfer():
        try:
            response = client.post(
                "/api/v1/transfers/",
                json={
                    "from_account_id": "RACER",
                    "to_account_id": "RECEIVER",
                    "amount": 20.00
                }
            )
            return "success" if response.status_code == 201 else "failed"
        except Exception:
            return "failed"
    
    # Launch 10 concurrent transfers
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_transfer) for _ in range(10)]
        results = [future.result() for future in as_completed(futures)]
    
    # Only 5 should succeed (5 * 20 = 100), rest should fail
    assert results.count("success") == 5
    assert results.count("failed") == 5
    
    # Balance should be exactly 0, never negative
    racer_balance = client.get("/api/v1/accounts/RACER/balance").json()
    assert float(racer_balance["balance"]) == 0.00


def test_concurrent_bidirectional_transfers():
    """
    Test Alice and Bob transferring to each other simultaneously.
    Tests deadlock prevention and consistency.
    """
    # Create accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "ALICE", "owner_name": "Alice", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "BOB", "owner_name": "Bob", "initial_balance": 1000.00}
    )
    
    def alice_to_bob():
        for _ in range(5):
            client.post(
                "/api/v1/transfers/",
                json={"from_account_id": "ALICE", "to_account_id": "BOB", "amount": 10.00}
            )
    
    def bob_to_alice():
        for _ in range(5):
            client.post(
                "/api/v1/transfers/",
                json={"from_account_id": "BOB", "to_account_id": "ALICE", "amount": 10.00}
            )
    
    # Run simultaneously
    thread1 = threading.Thread(target=alice_to_bob)
    thread2 = threading.Thread(target=bob_to_alice)
    
    thread1.start()
    thread2.start()
    
    thread1.join()
    thread2.join()
    
    # Net effect should be zero (5*10 each way = net 0)
    alice_balance = client.get("/api/v1/accounts/ALICE/balance").json()
    bob_balance = client.get("/api/v1/accounts/BOB/balance").json()
    
    assert float(alice_balance["balance"]) == 1000.00
    assert float(bob_balance["balance"]) == 1000.00


def test_concurrent_duplicate_transaction_ids():
    """
    Test multiple threads trying to process same transaction ID simultaneously.
    Only one should succeed (idempotency under concurrency).
    """
    # Create accounts
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "IDEMPOTENT_SRC", "owner_name": "Source", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "IDEMPOTENT_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    def try_transfer():
        try:
            response = client.post(
                "/api/v1/transfers/",
                json={
                    "from_account_id": "IDEMPOTENT_SRC",
                    "to_account_id": "IDEMPOTENT_DEST",
                    "amount": 100.00,
                    "transaction_id": "DUPLICATE_TEST_001"
                }
            )
            return "success" if response.status_code == 201 else "rejected"
        except Exception:
            return "rejected"
    
    # 10 threads try same transaction simultaneously
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_transfer) for _ in range(10)]
        results = [future.result() for future in as_completed(futures)]
    
    # Only 1 should succeed, rest rejected
    assert results.count("success") == 1
    assert results.count("rejected") == 9
    
    # Only £100 should be transferred (not £1000)
    src_balance = client.get("/api/v1/accounts/IDEMPOTENT_SRC/balance").json()
    dest_balance = client.get("/api/v1/accounts/IDEMPOTENT_DEST/balance").json()
    
    assert float(src_balance["balance"]) == 900.00
    assert float(dest_balance["balance"]) == 100.00


# ==================== EXTREME VALUE TESTS ====================

def test_very_large_transfer():
    """Test transferring very large amounts (near system limits)."""
    # Create account with 1 billion
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "WHALE", "owner_name": "Whale", "initial_balance": 999999999.99}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "RECEIVER", "owner_name": "Receiver", "initial_balance": 0.00}
    )
    
    # Transfer almost all of it
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "WHALE",
            "to_account_id": "RECEIVER",
            "amount": 999999999.00
        }
    )
    
    assert response.status_code == 201
    
    whale_balance = client.get("/api/v1/accounts/WHALE/balance").json()
    receiver_balance = client.get("/api/v1/accounts/RECEIVER/balance").json()
    
    assert float(whale_balance["balance"]) == 0.99
    assert float(receiver_balance["balance"]) == 999999999.00


def test_very_small_transfer():
    """Test transferring very small amounts (penny)."""
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "PENNY_SRC", "owner_name": "Source", "initial_balance": 100.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "PENNY_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    # Transfer 1 penny
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "PENNY_SRC",
            "to_account_id": "PENNY_DEST",
            "amount": 0.01
        }
    )
    
    assert response.status_code == 201
    
    src_balance = client.get("/api/v1/accounts/PENNY_SRC/balance").json()
    dest_balance = client.get("/api/v1/accounts/PENNY_DEST/balance").json()
    
    assert float(src_balance["balance"]) == 99.99
    assert float(dest_balance["balance"]) == 0.01


def test_many_small_transfers():
    """Test 100 small transfers to check accuracy and performance."""
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "MANY_SRC", "owner_name": "Source", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "MANY_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    # Transfer £10 a hundred times
    for i in range(100):
        response = client.post(
            "/api/v1/transfers/",
            json={
                "from_account_id": "MANY_SRC",
                "to_account_id": "MANY_DEST",
                "amount": 10.00
            }
        )
        assert response.status_code == 201
    
    # Verify final balances
    src_balance = client.get("/api/v1/accounts/MANY_SRC/balance").json()
    dest_balance = client.get("/api/v1/accounts/MANY_DEST/balance").json()
    
    assert float(src_balance["balance"]) == 0.00
    assert float(dest_balance["balance"]) == 1000.00
    
    # Verify transaction count
    transactions = client.get("/api/v1/transfers/account/MANY_SRC").json()
    assert len(transactions) == 100


def test_decimal_precision():
    """Test that decimal precision is maintained (no floating point errors)."""
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "PRECISE_SRC", "owner_name": "Source", "initial_balance": 100.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "PRECISE_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    # Transfer £0.33 three times (should be £0.99, not £1.00)
    for _ in range(3):
        client.post(
            "/api/v1/transfers/",
            json={
                "from_account_id": "PRECISE_SRC",
                "to_account_id": "PRECISE_DEST",
                "amount": 0.33
            }
        )
    
    src_balance = client.get("/api/v1/accounts/PRECISE_SRC/balance").json()
    dest_balance = client.get("/api/v1/accounts/PRECISE_DEST/balance").json()
    
    # Should be 99.01 and 0.99 (exact), not floating point errors
    assert float(src_balance["balance"]) == 99.01
    assert float(dest_balance["balance"]) == 0.99


# ==================== BUSINESS LOGIC EDGE CASES ====================

def test_transfer_exact_balance():
    """Test transferring exactly the account balance (edge case)."""
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "EXACT_SRC", "owner_name": "Source", "initial_balance": 100.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "EXACT_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    # Transfer exact balance
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "EXACT_SRC",
            "to_account_id": "EXACT_DEST",
            "amount": 100.00
        }
    )
    
    assert response.status_code == 201
    
    src_balance = client.get("/api/v1/accounts/EXACT_SRC/balance").json()
    dest_balance = client.get("/api/v1/accounts/EXACT_DEST/balance").json()
    
    assert float(src_balance["balance"]) == 0.00
    assert float(dest_balance["balance"]) == 100.00


def test_transfer_one_penny_over_balance():
    """Test that transfer fails if even 1 penny over balance."""
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "OVER_SRC", "owner_name": "Source", "initial_balance": 100.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "OVER_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    # Try to transfer £100.01 when balance is £100.00
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "OVER_SRC",
            "to_account_id": "OVER_DEST",
            "amount": 100.01
        }
    )
    
    assert response.status_code == 400
    assert "Insufficient funds" in response.json()["detail"]
    
    # Balance should be unchanged
    src_balance = client.get("/api/v1/accounts/OVER_SRC/balance").json()
    assert float(src_balance["balance"]) == 100.00


def test_zero_balance_account_operations():
    """Test operations on account with zero balance."""
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "ZERO_SRC", "owner_name": "Zero", "initial_balance": 0.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "ZERO_DEST", "owner_name": "Dest", "initial_balance": 100.00}
    )
    
    # Can't transfer from zero balance
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "ZERO_SRC",
            "to_account_id": "ZERO_DEST",
            "amount": 1.00
        }
    )
    assert response.status_code == 400
    
    # Can receive transfers
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "ZERO_DEST",
            "to_account_id": "ZERO_SRC",
            "amount": 50.00
        }
    )
    assert response.status_code == 201
    
    zero_balance = client.get("/api/v1/accounts/ZERO_SRC/balance").json()
    assert float(zero_balance["balance"]) == 50.00


def test_complex_multi_account_scenario():
    """
    Complex scenario: Multiple accounts with various transfers.
    Tests overall system consistency.
    """
    # Create 5 accounts
    for i in range(5):
        client.post(
            "/api/v1/accounts/",
            json={
                "account_id": f"COMPLEX{i}",
                "owner_name": f"User{i}",
                "initial_balance": 1000.00
            }
        )
    
    # Total money in system
    initial_total = 5000.00
    
    # Perform complex transfers
    client.post("/api/v1/transfers/", json={"from_account_id": "COMPLEX0", "to_account_id": "COMPLEX1", "amount": 100.00})
    client.post("/api/v1/transfers/", json={"from_account_id": "COMPLEX1", "to_account_id": "COMPLEX2", "amount": 200.00})
    client.post("/api/v1/transfers/", json={"from_account_id": "COMPLEX2", "to_account_id": "COMPLEX3", "amount": 150.00})
    client.post("/api/v1/transfers/", json={"from_account_id": "COMPLEX3", "to_account_id": "COMPLEX4", "amount": 300.00})
    client.post("/api/v1/transfers/", json={"from_account_id": "COMPLEX4", "to_account_id": "COMPLEX0", "amount": 250.00})
    
    # Total should remain the same (conservation of money)
    final_total = 0.0
    for i in range(5):
        balance = client.get(f"/api/v1/accounts/COMPLEX{i}/balance").json()
        final_total += float(balance["balance"])
    
    assert final_total == initial_total


# ==================== STRESS TESTS ====================

def test_high_volume_sequential_transfers():
    """
    Stress test: Process 500 sequential transactions.
    Tests performance and memory handling.
    """
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "STRESS_SRC", "owner_name": "Source", "initial_balance": 100000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "STRESS_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    # Process 500 transfers of £10 each
    for i in range(500):
        response = client.post(
            "/api/v1/transfers/",
            json={
                "from_account_id": "STRESS_SRC",
                "to_account_id": "STRESS_DEST",
                "amount": 10.00,
                "description": f"Transfer {i}"
            }
        )
        assert response.status_code == 201
    
    # Verify final state
    src_balance = client.get("/api/v1/accounts/STRESS_SRC/balance").json()
    dest_balance = client.get("/api/v1/accounts/STRESS_DEST/balance").json()
    
    assert float(src_balance["balance"]) == 95000.00
    assert float(dest_balance["balance"]) == 5000.00
    
    # Verify all transactions recorded
    transactions = client.get("/api/v1/transfers/account/STRESS_SRC?limit=1000").json()
    assert len(transactions) == 500


def test_long_description():
    """Test transaction with very long description."""
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "DESC_SRC", "owner_name": "Source", "initial_balance": 1000.00}
    )
    client.post(
        "/api/v1/accounts/",
        json={"account_id": "DESC_DEST", "owner_name": "Dest", "initial_balance": 0.00}
    )
    
    long_desc = "A" * 500  # 500 character description (at limit)
    
    response = client.post(
        "/api/v1/transfers/",
        json={
            "from_account_id": "DESC_SRC",
            "to_account_id": "DESC_DEST",
            "amount": 100.00,
            "description": long_desc
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == long_desc