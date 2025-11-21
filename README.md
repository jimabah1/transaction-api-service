# Transaction API Service

Production-grade REST API for payment processing with database persistence, built with FastAPI and PostgreSQL.

## Features

- **Account Management**: Create, retrieve, and manage financial accounts
- **Money Transfers**: Process transfers with atomicity and double-entry bookkeeping
- **Concurrency Safe**: Row-level locking prevents race conditions
- **Idempotency**: Duplicate transaction prevention
- **Comprehensive Testing**: 34 tests covering API, concurrency, stress, and edge cases
- **Auto-generated Documentation**: Interactive Swagger UI and ReDoc
- **Production Ready**: PostgreSQL, Docker support, error handling

## Tech Stack

- **Framework**: FastAPI 0.104+
- **Database**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0
- **Testing**: pytest with 100% pass rate (34/34 tests)
- **Containerization**: Docker & Docker Compose
- **Authentication**: JWT (ready for implementation)

## API Endpoints

### Accounts
- `POST /api/v1/accounts/` - Create account
- `GET /api/v1/accounts/` - List all accounts
- `GET /api/v1/accounts/{id}` - Get account details
- `GET /api/v1/accounts/{id}/balance` - Get account balance
- `DELETE /api/v1/accounts/{id}` - Delete account

### Transfers
- `POST /api/v1/transfers/` - Create transfer
- `GET /api/v1/transfers/` - List all transfers
- `GET /api/v1/transfers/{id}` - Get transfer details
- `GET /api/v1/transfers/account/{id}` - Get account's transfers

## Quick Start

### Using Docker (Recommended)
```bash
# Clone repository
git clone https://github.com/yourusername/transaction-api-service.git
cd transaction-api-service

# Start services
docker-compose up --build

# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Local Development

**Prerequisites:**
- Python 3.11+
- PostgreSQL 16+

**Setup:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run database migrations (tables auto-created on startup)

# Start server
uvicorn app.main:app --reload
```

## Testing
```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html -v

# Run specific test suite
pytest tests/test_api.py -v          # API tests (19 tests)
pytest tests/test_advanced.py -v     # Advanced tests (15 tests)
```

### Test Coverage

- **Basic API Tests (19/19)**: CRUD operations, validation, error handling
- **Advanced Tests (15/15)**:
  - Concurrency tests (50 concurrent accounts, 100 concurrent transfers)
  - Race condition handling
  - Deadlock prevention
  - Stress tests (500+ sequential operations)
  - Edge cases (extreme values, decimal precision)

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Architecture
```
transaction-api-service/
├── app/
│   ├── api/
│   │   ├── accounts.py       # Account endpoints
│   │   └── transfers.py      # Transfer endpoints
│   ├── core/
│   │   └── config.py         # Configuration
│   ├── models/
│   │   ├── account.py        # Account model
│   │   └── transaction.py    # Transaction model
│   ├── schemas/
│   │   ├── account.py        # Pydantic schemas
│   │   └── transaction.py
│   ├── database.py           # Database connection
│   └── main.py               # FastAPI app
├── tests/
│   ├── test_api.py           # API tests
│   └── test_advanced.py      # Concurrency & stress tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Key Features Explained

### Atomicity
All transfers use database transactions - they either complete fully or fail completely.

### Concurrency Safety
Row-level locking (`SELECT FOR UPDATE`) prevents race conditions when multiple requests access the same account simultaneously.

### Idempotency
Custom transaction IDs prevent duplicate processing of the same transfer.

### Double-Entry Bookkeeping
Every transfer debits one account and credits another, maintaining system-wide balance.

## Configuration

Environment variables (set in `.env`):
```env
DATABASE_URL=postgresql://user:password@localhost:5432/transaction_api
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Example Usage

### Create Accounts
```bash
curl -X POST "http://localhost:8000/api/v1/accounts/" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "ACC001",
    "owner_name": "John Doe",
    "initial_balance": 1000.00
  }'
```

### Make Transfer
```bash
curl -X POST "http://localhost:8000/api/v1/transfers/" \
  -H "Content-Type: application/json" \
  -d '{
    "from_account_id": "ACC001",
    "to_account_id": "ACC002",
    "amount": 250.00,
    "description": "Payment for services"
  }'
```

## Future Enhancements

- [ ] JWT Authentication implementation
- [ ] Rate limiting
- [ ] Webhook notifications
- [ ] Transaction history pagination
- [ ] CSV export functionality
- [ ] Admin dashboard

## License

MIT License

## Author

**Jimmah Abah**
- GitHub: [@jimabah1](https://github.com/jimabah1)
- LinkedIn: [Jimmah Abah](https://www.linkedin.com/in/jimmah-a-046914211)

## Acknowledgments

Built as part of a portfolio project demonstrating production-grade API development with focus on:
- Financial transaction processing
- Concurrent request handling
- Database transaction management
- Comprehensive testing strategies
