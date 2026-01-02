# backend/app/core/config.py
"""
Configuration settings for the application.
TEMPORARY FIX: Minimal config to support startup.
"""
import os
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://tafon_user:tafon_pass@localhost:5432/tafon_central_db"
    )
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # CORS
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    def show_config(self):
        """Print configuration (for debugging)."""
        print("=" * 50)
        print("Configuration loaded:")
        print(f"  DATABASE_URL: {self.DATABASE_URL[:30]}...")
        print(f"  ENVIRONMENT: {self.ENVIRONMENT}")
        print(f"  ACCESS_TOKEN_EXPIRE_MINUTES: {self.ACCESS_TOKEN_EXPIRE_MINUTES}")
        print("=" * 50)


settings = Settings()
