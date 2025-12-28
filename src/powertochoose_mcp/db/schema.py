"""Database schema definitions using SQLAlchemy ORM."""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Plan(Base):
    """Electricity plan model."""

    __tablename__ = "plans"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    zip_code = Column(String, nullable=False, index=True)
    contract_length_months = Column(Integer)
    renewable_percentage = Column(Integer)
    cancellation_fee = Column(Float)

    # Calculator data (stored as JSON)
    rate_structure = Column(JSON, nullable=False)
    cost_500_kwh = Column(JSON, nullable=False)
    cost_1000_kwh = Column(JSON, nullable=False)
    cost_2000_kwh = Column(JSON, nullable=False)

    # Metadata
    scraped_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    efl_url = Column(String)
    plan_url = Column(String)
    efl_parsed = Column(Integer, default=1)  # 1=success, 0=failed

    # Relationships
    classifications = relationship("PlanClassification", back_populates="plan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Plan(id={self.id}, name={self.name}, provider={self.provider})>"


class PlanClassification(Base):
    """Plan classification tags (many-to-many relationship)."""

    __tablename__ = "plan_classifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    classification = Column(String, nullable=False)  # e.g., "green", "ev", "time_of_use"
    source = Column(String, nullable=False)  # "website" or "derived"

    # Relationships
    plan = relationship("Plan", back_populates="classifications")

    # Constraints
    __table_args__ = (
        UniqueConstraint("plan_id", "classification", name="uix_plan_classification"),
        Index("idx_classification", "classification"),
    )

    def __repr__(self):
        return f"<PlanClassification(plan_id={self.plan_id}, classification={self.classification})>"


class RequestLog(Base):
    """Log of MCP tool requests for pattern analysis."""

    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    tool_name = Column(String, nullable=False)
    parameters = Column(JSON, nullable=False)
    result_count = Column(Integer)
    classifications_used = Column(JSON)

    def __repr__(self):
        return f"<RequestLog(id={self.id}, tool={self.tool_name}, timestamp={self.timestamp})>"
