"""Pydantic models for data validation."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class RateTier(BaseModel):
    """Rate tier for tiered pricing."""

    tier: str = Field(..., description="Tier description (e.g., '0-500', '500+')")
    kwh: int = Field(..., description="kWh usage in this tier")
    rate: float = Field(..., description="Rate per kWh in dollars")
    cost: float = Field(..., description="Total cost for this tier in dollars")


class CostBreakdown(BaseModel):
    """Cost breakdown at a specific usage level."""

    usage_kwh: int = Field(..., description="Usage level in kWh")
    base_charge_usd: float = Field(..., description="Monthly base charge")
    energy_charge_usd: float = Field(..., description="Total energy charge")
    energy_rate_per_kwh: float = Field(..., description="Average energy rate")
    tdu_delivery_usd: float = Field(..., description="TDU delivery charges")
    taxes_fees_usd: float = Field(..., description="Taxes and fees")
    total_monthly_usd: float = Field(..., description="Total monthly cost")
    breakdown_by_tier: List[RateTier] = Field(default_factory=list, description="Tier-by-tier breakdown")


class RateStructure(BaseModel):
    """Electricity rate structure parsed from EFL."""

    plan_type: str = Field(..., description="Plan type (fixed, variable, time_of_use)")
    base_charge: float = Field(..., description="Monthly base charge in dollars")
    tiers: List[Dict[str, Any]] = Field(default_factory=list, description="Rate tiers")
    tdu_delivery_rate: Optional[float] = Field(None, description="TDU delivery rate per kWh")
    renewable_percentage: Optional[int] = Field(None, description="Renewable energy percentage")
    has_time_of_use: bool = Field(default=False, description="Whether plan has time-of-use rates")
    early_termination_fee: Optional[float] = Field(None, description="Early termination fee")


class PlanData(BaseModel):
    """Complete plan data model."""

    id: str = Field(..., description="Unique plan identifier")
    name: str = Field(..., description="Plan name")
    provider: str = Field(..., description="Provider/REP name")
    zip_code: str = Field(..., description="ZIP code")
    contract_length_months: Optional[int] = Field(None, description="Contract length in months")
    renewable_percentage: Optional[int] = Field(None, description="Renewable energy percentage")
    cancellation_fee: Optional[float] = Field(None, description="Cancellation fee in dollars")

    # Calculator data
    rate_structure: Dict[str, Any] = Field(..., description="Parsed rate structure")
    cost_500_kwh: Dict[str, Any] = Field(..., description="Cost breakdown at 500 kWh")
    cost_1000_kwh: Dict[str, Any] = Field(..., description="Cost breakdown at 1000 kWh")
    cost_2000_kwh: Dict[str, Any] = Field(..., description="Cost breakdown at 2000 kWh")

    # Metadata
    efl_url: Optional[str] = Field(None, description="EFL PDF URL")
    plan_url: Optional[str] = Field(None, description="Plan details page URL")
    efl_parsed: bool = Field(default=True, description="Whether EFL was successfully parsed")

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str) -> str:
        """Validate ZIP code format."""
        if not v.isdigit() or len(v) != 5:
            raise ValueError("ZIP code must be 5 digits")
        return v


class SearchParams(BaseModel):
    """Parameters for search_plans tool."""

    zip_code: str = Field(..., description="5-digit ZIP code")
    classifications: Optional[List[str]] = Field(default=None, description="Plan classifications to filter by")
    max_results: Optional[int] = Field(default=None, description="Maximum number of results")

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str) -> str:
        """Validate ZIP code format."""
        if not v.isdigit() or len(v) != 5:
            raise ValueError("ZIP code must be 5 digits")
        return v


class CalculateParams(BaseModel):
    """Parameters for calculate_plan_cost tool."""

    plan_id: str = Field(..., description="Plan identifier")


class PlanSummary(BaseModel):
    """Summary of a plan for search results."""

    id: str
    name: str
    provider: str
    contract_length_months: Optional[int]
    renewable_percentage: Optional[int]
    classifications: List[str]
    cost_at_1000_kwh: float
    rate_structure_summary: str
    scraped_at: datetime


class PlanCostDetail(BaseModel):
    """Detailed cost information for a plan."""

    plan_id: str
    plan_name: str
    provider: str
    cost_500_kwh: CostBreakdown
    cost_1000_kwh: CostBreakdown
    cost_2000_kwh: CostBreakdown
    rate_structure: Dict[str, Any]
    scraped_at: datetime
