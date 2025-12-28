"""Configuration settings for PowerToChoose MCP Server."""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "powertochoose.db"))
EFL_DIR = Path(os.getenv("EFL_DIR", DATA_DIR / "efls"))
LOG_DIR = Path(os.getenv("LOG_DIR", DATA_DIR / "logs"))

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
EFL_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Initial ZIP codes (North Texas - Frisco area)
ZIP_CODES = [
    "75035",  # Frisco
    "75024",  # Plano (west)
    "75074",  # Plano (east)
    "75093",  # Plano (north)
    "75034",  # Frisco (north)
    "75033",  # Frisco (south)
    "75070",  # McKinney
]

# Usage tiers for cost calculation (kWh per month)
USAGE_TIERS = [500, 1000, 2000]

# Data retention policies (in days)
EFL_RETENTION_DAYS = 2
LOG_RETENTION_DAYS = 90
PLAN_RETENTION_DAYS = 7

# Scraping configuration
POWERTOCHOOSE_BASE_URL = "http://www.powertochoose.org"
REQUEST_DELAY_SECONDS = 1.0  # Delay between requests to respect rate limits
REQUEST_TIMEOUT_SECONDS = 30.0

# Database configuration
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
SQLALCHEMY_CONNECT_ARGS = {"check_same_thread": False}

# Enable WAL mode for SQLite (better concurrent access)
SQLITE_ENABLE_WAL = True
