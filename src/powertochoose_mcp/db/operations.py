"""Database operations and queries."""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker, Session

from ..config import (
    SQLALCHEMY_DATABASE_URL,
    SQLALCHEMY_CONNECT_ARGS,
    SQLITE_ENABLE_WAL,
)
from .schema import Base, Plan, PlanClassification, RequestLog


# Create engine and session factory
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=SQLALCHEMY_CONNECT_ARGS,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_session():
    """Get a database session with automatic cleanup."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """Initialize the database and enable WAL mode for SQLite."""
    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Enable WAL mode for better concurrent access
    if SQLITE_ENABLE_WAL:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()


def store_plan(session: Session, plan_data: dict, classifications: List[str]) -> Plan:
    """Store or update a plan in the database.

    Args:
        session: Database session
        plan_data: Dictionary containing plan fields
        classifications: List of classification tags

    Returns:
        Stored Plan object
    """
    # Check if plan already exists
    existing_plan = session.query(Plan).filter(Plan.id == plan_data["id"]).first()

    if existing_plan:
        # Update existing plan
        for key, value in plan_data.items():
            setattr(existing_plan, key, value)
        existing_plan.scraped_at = datetime.utcnow()
        plan = existing_plan

        # Remove old classifications
        session.query(PlanClassification).filter(
            PlanClassification.plan_id == plan.id
        ).delete()
    else:
        # Create new plan
        plan = Plan(**plan_data)
        session.add(plan)

    # Add classifications
    for classification in classifications:
        plan_classification = PlanClassification(
            plan_id=plan.id,
            classification=classification,
            source="website",
        )
        session.add(plan_classification)

    session.flush()
    return plan


def get_plans_by_zip(
    session: Session,
    zip_code: str,
    classifications: Optional[List[str]] = None,
    only_complete: bool = True,
) -> List[Plan]:
    """Get plans for a specific ZIP code.

    Args:
        session: Database session
        zip_code: ZIP code to filter by
        classifications: Optional list of classifications to filter by
        only_complete: If True, only return plans with successful EFL parsing

    Returns:
        List of Plan objects
    """
    query = session.query(Plan).filter(Plan.zip_code == zip_code)

    if only_complete:
        query = query.filter(Plan.efl_parsed == 1)

    if classifications:
        # Filter by classifications (plans must have at least one matching classification)
        query = query.join(PlanClassification).filter(
            PlanClassification.classification.in_(classifications)
        )

    return query.order_by(Plan.name).all()


def get_plan_by_id(session: Session, plan_id: str) -> Optional[Plan]:
    """Get a plan by its ID.

    Args:
        session: Database session
        plan_id: Plan identifier

    Returns:
        Plan object or None if not found
    """
    return session.query(Plan).filter(Plan.id == plan_id).first()


def log_request(session: Session, tool_name: str, parameters: dict, result_count: int):
    """Log an MCP tool request.

    Args:
        session: Database session
        tool_name: Name of the MCP tool
        parameters: Tool parameters
        result_count: Number of results returned
    """
    classifications_used = parameters.get("classifications")

    log_entry = RequestLog(
        tool_name=tool_name,
        parameters=parameters,
        result_count=result_count,
        classifications_used=classifications_used,
    )
    session.add(log_entry)
    session.flush()


def cleanup_old_data(session: Session, retention_days: int):
    """Remove plans older than retention period.

    Args:
        session: Database session
        retention_days: Number of days to retain data
    """
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    session.query(Plan).filter(Plan.scraped_at < cutoff_date).delete()
    session.flush()


def cleanup_old_logs(session: Session, retention_days: int):
    """Remove request logs older than retention period.

    Args:
        session: Database session
        retention_days: Number of days to retain logs
    """
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    session.query(RequestLog).filter(RequestLog.timestamp < cutoff_date).delete()
    session.flush()
