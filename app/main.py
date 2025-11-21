"""
Main FastAPI application entry point.
Sets up the API, middleware, and routes.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database import engine, Base
from app.api import accounts, transfers

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc UI
)

# CORS middleware (allows frontend to call API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """
    Root endpoint - health check.
    """
    return {
        "message": "Transaction API Service",
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "accounts": f"{settings.API_V1_PREFIX}/accounts",
            "transfers": f"{settings.API_V1_PREFIX}/transfers"
        }
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {
        "status": "healthy",
        "database": "connected"
    }


# Include API routers
app.include_router(accounts.router, prefix=settings.API_V1_PREFIX)
app.include_router(transfers.router, prefix=settings.API_V1_PREFIX)