"""
FastAPI server for public API access to PowerToChoose MCP server.

This server provides HTTP endpoints for analyzing electricity usage and recommending plans.
It wraps the MCP server and Google ADK agent to provide a clean REST API.
"""

import os
import io
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from apscheduler.schedulers.background import BackgroundScheduler

from google import genai
from google.adk import agents
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/sse")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "https://dijit.tech").split(",")
UPLOAD_DIR = "/app/uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
RETENTION_HOURS = 1

# Supported ZIP codes (from config)
SUPPORTED_ZIPS = ["75035", "75024", "75074", "75093", "75034", "75033", "75070"]

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Global ADK agent (initialized in lifespan)
search_agent = None
power_plan_finder = None


# Pydantic models
class AnalyzeRequest(BaseModel):
    """Request model for CSV analysis."""
    zip_code: str
    
    @validator('zip_code')
    def validate_zip(cls, v):
        if not v.isdigit() or len(v) != 5:
            raise ValueError('Invalid ZIP code format')
        if v not in SUPPORTED_ZIPS:
            raise ValueError(f'ZIP code {v} not yet supported. Currently available: {", ".join(SUPPORTED_ZIPS)}')
        return v


class UsageAnalysis(BaseModel):
    """Usage pattern analysis results."""
    avg_monthly_kwh: float
    peak_time: str
    peak_to_offpeak_ratio: float
    pattern_type: str  # "time_of_use", "flat", "evening_peak"
    meter_id: str


class PlanBreakdown(BaseModel):
    """Cost breakdown for a plan."""
    base_charge_usd: float
    energy_charge_usd: float
    tdu_delivery_usd: float
    taxes_fees_usd: float
    total_monthly_usd: float


class PlanRecommendation(BaseModel):
    """Single plan recommendation."""
    plan_id: str
    plan_name: str
    provider: str
    monthly_cost: float
    renewable_percentage: int
    contract_months: int
    cancellation_fee: Optional[float]
    breakdown: PlanBreakdown
    rating: str  # "excellent", "good", "fair"
    recommendation_reason: str


class AnalyzeResponse(BaseModel):
    """Response model for analysis endpoint."""
    status: str
    recommendations: List[PlanRecommendation]
    usage_analysis: UsageAnalysis
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    mcp_server: bool
    database: Dict[str, Any]
    api: Dict[str, Any]


# Cleanup scheduler
scheduler = BackgroundScheduler()


def cleanup_old_uploads():
    """Delete uploaded files older than RETENTION_HOURS."""
    if not os.path.exists(UPLOAD_DIR):
        return
    
    now = time.time()
    deleted_count = 0
    
    for filename in os.listdir(UPLOAD_DIR):
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > RETENTION_HOURS * 3600:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.info(f"Deleted old upload: {filename}")
                except Exception as e:
                    logger.error(f"Failed to delete {filename}: {e}")
    
    if deleted_count > 0:
        logger.info(f"Cleanup: Deleted {deleted_count} old upload(s)")


def initialize_adk_agents():
    """Initialize Google ADK agents."""
    global search_agent, power_plan_finder
    
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set - agents will not be initialized")
        return
    
    try:
        # Initialize Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Create MCP toolset
        powertochoose_toolset = McpToolset(
            connection_params=SseConnectionParams(url=MCP_SERVER_URL)
        )
        
        # Create Search Agent
        search_agent = agents.create(
            name="search_agent",
            model="gemini-2.0-flash-exp",
            instruction="""You are a Texas electricity plan search specialist with access to real-time plan data.

**Your capabilities:**
1. Search electricity plans by ZIP code using the `search_plans` tool
2. Calculate detailed costs for specific plans using the `calculate_plan_cost` tool
3. Filter plans by classifications (green, time_of_use, etc.)

**Always:**
- Use search_plans to find available plans for the user's ZIP code
- Use calculate_plan_cost to get detailed cost breakdowns
- Return structured data with plan names, costs, and provider information
- Recommend 2-3 plans that best match the user's usage pattern

**Response format:**
- Plan name, provider, monthly cost estimate
- Renewable percentage, contract length
- Cost breakdown (base charge, energy charge, TDU, taxes)
- Brief explanation of why this plan fits the usage pattern""",
            toolsets=[powertochoose_toolset]
        )
        
        # Create Power Plan Finder (orchestrator)
        power_plan_finder = agents.create(
            name="power_plan_finder",
            model="gemini-2.0-flash-exp",
            instruction="""You are the main electricity plan recommendation agent.

**Workflow:**
1. Analyze the user's usage pattern (provided in the request)
2. Determine best plan type (flat rate, time-of-use, green energy, etc.)
3. Delegate to search_agent to find matching plans
4. Return top 2-3 recommendations with cost comparisons

**Key factors to consider:**
- Average monthly usage (kWh)
- Peak usage time (indicates time-of-use benefit)
- User preferences (renewable energy, contract length)
- Cost at user's specific usage level

**Response format:**
- List of 2-3 recommended plans
- Clear cost comparison
- Explanation of why each plan was chosen""",
            agents=[search_agent]
        )
        
        logger.info("ADK agents initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize ADK agents: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting PowerToChoose API server...")
    
    # Create upload directory
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Initialize ADK agents
    initialize_adk_agents()
    
    # Start cleanup scheduler
    scheduler.add_job(cleanup_old_uploads, 'interval', minutes=15)
    scheduler.start()
    logger.info("Cleanup scheduler started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down PowerToChoose API server...")
    scheduler.shutdown()


# Create FastAPI app
app = FastAPI(
    title="PowerToChoose API",
    description="Public API for Texas electricity plan recommendations",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def analyze_meter_csv(df: pd.DataFrame) -> UsageAnalysis:
    """
    Analyze meter data CSV and extract usage patterns.
    
    Expected columns: Date, Usage, Reading Type
    """
    # Filter for actual usage readings
    usage_df = df[df['Reading Type'] == 'Actual'].copy()
    
    if len(usage_df) == 0:
        raise ValueError("No actual usage readings found in CSV")
    
    # Convert date and usage
    usage_df['Date'] = pd.to_datetime(usage_df['Date'])
    usage_df['Usage'] = pd.to_numeric(usage_df['Usage'], errors='coerce')
    
    # Calculate daily average
    daily_avg = usage_df.groupby(usage_df['Date'].dt.date)['Usage'].sum().mean()
    monthly_avg = daily_avg * 30
    
    # Detect peak time (if hourly data available)
    if 'Hour' in usage_df.columns or len(usage_df) > 100:
        usage_df['Hour'] = usage_df['Date'].dt.hour
        hourly_avg = usage_df.groupby('Hour')['Usage'].mean()
        peak_hour = hourly_avg.idxmax()
        peak_time = f"{peak_hour:02d}:00"
        
        # Calculate peak-to-offpeak ratio
        peak_usage = hourly_avg.loc[peak_hour]
        offpeak_hours = [0, 1, 2, 3, 4, 5, 6]  # Typical off-peak
        offpeak_usage = hourly_avg.loc[offpeak_hours].mean() if any(h in hourly_avg.index for h in offpeak_hours) else hourly_avg.min()
        peak_ratio = peak_usage / offpeak_usage if offpeak_usage > 0 else 1.0
    else:
        peak_time = "20:00"  # Default evening peak
        peak_ratio = 1.5  # Moderate variation
    
    # Determine pattern type
    if peak_ratio > 2.5:
        pattern_type = "time_of_use"
    elif peak_ratio > 1.8:
        pattern_type = "evening_peak"
    else:
        pattern_type = "flat"
    
    # Extract meter ID (if available)
    meter_id = df['ESIID'].iloc[0] if 'ESIID' in df.columns else "unknown"
    
    return UsageAnalysis(
        avg_monthly_kwh=round(monthly_avg, 1),
        peak_time=peak_time,
        peak_to_offpeak_ratio=round(peak_ratio, 2),
        pattern_type=pattern_type,
        meter_id=str(meter_id)
    )


async def get_plan_recommendations(usage_analysis: UsageAnalysis, zip_code: str) -> List[Dict[str, Any]]:
    """
    Get plan recommendations from ADK agent.
    
    Returns raw agent response that needs to be parsed.
    """
    if not power_plan_finder:
        raise HTTPException(status_code=503, detail="Agent not initialized - check GEMINI_API_KEY")
    
    prompt = f"""Analyze this electricity usage and recommend the best plans:

ZIP Code: {zip_code}
Average Monthly Usage: {usage_analysis.avg_monthly_kwh} kWh
Peak Usage Time: {usage_analysis.peak_time}
Peak-to-Off-Peak Ratio: {usage_analysis.peak_to_offpeak_ratio}x
Usage Pattern: {usage_analysis.pattern_type}

Find 2-3 best electricity plans that:
1. Match this usage pattern
2. Provide best value at {usage_analysis.avg_monthly_kwh} kWh/month
3. Include cost breakdowns

Use search_agent to find and calculate costs for plans in ZIP {zip_code}."""
    
    try:
        # Generate response from agent
        response = await power_plan_finder.generate_async(prompt=prompt)
        
        # Parse agent response (simplified - production would need better parsing)
        # For MVP, we'll return the agent's text response
        return {"agent_response": response.text, "raw_response": str(response)}
        
    except Exception as e:
        logger.error(f"Agent generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/api/analyze", response_model=AnalyzeResponse)
@limiter.limit("10/hour")
async def analyze_csv(
    request: Request,
    csv_file: UploadFile = File(...),
    zip_code: str = Form(...)
):
    """
    Analyze electricity usage CSV and recommend plans.
    
    Rate limit: 10 requests per hour per IP (anonymous users)
    """
    logger.info(f"Analysis request from {request.client.host} for ZIP {zip_code}")
    
    # Validate ZIP code
    try:
        request_data = AnalyzeRequest(zip_code=zip_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Validate file
    if not csv_file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    
    # Read and validate file size
    contents = await csv_file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_FILE_SIZE/1024/1024}MB)")
    
    # Save temporarily
    timestamp = int(time.time())
    filename = f"{timestamp}_{csv_file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    try:
        with open(filepath, "wb") as f:
            f.write(contents)
        
        # Parse CSV
        try:
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
        
        # Analyze usage
        try:
            usage_analysis = analyze_meter_csv(df)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"CSV analysis failed: {str(e)}")
        
        # Get recommendations from agent
        recommendations_raw = await get_plan_recommendations(usage_analysis, zip_code)
        
        # TODO: Parse agent response into structured PlanRecommendation objects
        # For MVP, return mock data structure
        mock_recommendations = [
            PlanRecommendation(
                plan_id="mock_1",
                plan_name="Sample Plan (Agent Integration Pending)",
                provider="SAMPLE REP",
                monthly_cost=round(usage_analysis.avg_monthly_kwh * 0.12, 2),
                renewable_percentage=50,
                contract_months=12,
                cancellation_fee=150.0,
                breakdown=PlanBreakdown(
                    base_charge_usd=9.95,
                    energy_charge_usd=round(usage_analysis.avg_monthly_kwh * 0.08, 2),
                    tdu_delivery_usd=round(usage_analysis.avg_monthly_kwh * 0.03, 2),
                    taxes_fees_usd=5.0,
                    total_monthly_usd=round(usage_analysis.avg_monthly_kwh * 0.12, 2)
                ),
                rating="good",
                recommendation_reason=f"Matches your {usage_analysis.pattern_type} usage pattern"
            )
        ]
        
        logger.info(f"Analysis complete for ZIP {zip_code}: {usage_analysis.avg_monthly_kwh} kWh/month")
        
        return AnalyzeResponse(
            status="success",
            recommendations=mock_recommendations,
            usage_analysis=usage_analysis,
            message=f"Found {len(mock_recommendations)} recommended plan(s). Agent response: {recommendations_raw.get('agent_response', '')[:100]}..."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    finally:
        # Cleanup happens via scheduler
        pass


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    import httpx
    from powertochoose_mcp.db import operations
    
    # Check MCP server
    mcp_healthy = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(MCP_SERVER_URL.replace("/sse", "/health") if "/sse" in MCP_SERVER_URL else MCP_SERVER_URL, timeout=2.0)
            mcp_healthy = response.status_code == 200
    except:
        mcp_healthy = False
    
    # Check database
    try:
        plan_count = operations.get_plan_count()
        last_scrape = operations.get_last_scrape_time()
        db_info = {
            "total_plans": plan_count,
            "last_scrape": last_scrape.isoformat() if last_scrape else None,
            "zips_covered": SUPPORTED_ZIPS
        }
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        db_info = {"error": str(e)}
    
    return HealthResponse(
        status="healthy" if mcp_healthy else "degraded",
        mcp_server=mcp_healthy,
        database=db_info,
        api={
            "agents_initialized": power_plan_finder is not None,
            "upload_dir_exists": os.path.exists(UPLOAD_DIR),
            "supported_zips": len(SUPPORTED_ZIPS)
        }
    )


@app.get("/api/plans/{zip_code}")
@limiter.limit("30/hour")
async def get_plans(request: Request, zip_code: str, renewable: Optional[bool] = None, max_months: Optional[int] = None):
    """
    Browse available plans for a ZIP code.
    
    Rate limit: 30 requests per hour per IP
    """
    # Validate ZIP code
    if zip_code not in SUPPORTED_ZIPS:
        raise HTTPException(
            status_code=400, 
            detail=f"ZIP {zip_code} not supported. Available: {', '.join(SUPPORTED_ZIPS)}"
        )
    
    # TODO: Query database directly for browsing
    # For MVP, return placeholder
    return {
        "zip_code": zip_code,
        "filters": {"renewable": renewable, "max_contract_months": max_months},
        "plans": [],
        "message": "Browse endpoint coming soon - use /api/analyze for recommendations"
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "PowerToChoose API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "endpoints": {
            "POST /api/analyze": "Upload CSV and get plan recommendations",
            "GET /api/plans/{zip_code}": "Browse available plans",
            "GET /api/health": "Server health check"
        },
        "rate_limits": {
            "analyze": "10 requests/hour",
            "browse": "30 requests/hour"
        },
        "supported_zips": SUPPORTED_ZIPS
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
