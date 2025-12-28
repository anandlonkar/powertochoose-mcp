"""MCP server implementation.

Exposes search_plans and calculate_plan_cost tools to LLMs via Model Context Protocol.
"""

import json
import sys
from typing import List, Dict, Any
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import Response

from .db import get_session, get_plans_by_zip, get_plan_by_id, log_request
from .models import SearchParams, CalculateParams, PlanSummary, PlanCostDetail, CostBreakdown
from .config import ZIP_CODES
from .utils.logging import log_request_to_jsonl


# Create MCP server instance
app = Server("powertochoose-mcp")


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="search_plans",
            description="Search electricity plans by ZIP code with optional classification filters. "
            "Returns plans with complete calculator data for the specified area.",
            inputSchema={
                "type": "object",
                "properties": {
                    "zip_code": {
                        "type": "string",
                        "description": "5-digit ZIP code (North Texas area)",
                    },
                    "classifications": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Filter by plan classifications (green, ev, time_of_use, fixed_rate, etc.)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Optional: Maximum number of results to return",
                    },
                },
                "required": ["zip_code"],
            },
        ),
        Tool(
            name="calculate_plan_cost",
            description="Calculate detailed cost breakdown for a specific plan at 500, 1000, and 2000 kWh usage levels. "
            "Returns base charges, energy charges by tier, TDU delivery, taxes, and total monthly cost.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": "Plan identifier from search results",
                    },
                },
                "required": ["plan_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle MCP tool calls."""
    if name == "search_plans":
        return await search_plans_tool(arguments)
    elif name == "calculate_plan_cost":
        return await calculate_plan_cost_tool(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def search_plans_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """Search electricity plans by ZIP code.

    Args:
        arguments: Tool arguments

    Returns:
        List of TextContent with search results
    """
    # Validate parameters
    params = SearchParams(**arguments)

    # Check if ZIP code is supported
    if params.zip_code not in ZIP_CODES:
        result = {
            "message": "Service coming to your ZIP code soon!",
            "supported_zip_codes": ZIP_CODES,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Query database
    with get_session() as session:
        plans = get_plans_by_zip(
            session,
            params.zip_code,
            classifications=params.classifications,
            only_complete=True,
        )

        # Limit results if requested
        if params.max_results:
            plans = plans[:params.max_results]

        # Convert to summaries
        summaries = []
        for plan in plans:
            # Get classifications
            classifications = [c.classification for c in plan.classifications]

            # Create summary
            summary = PlanSummary(
                id=plan.id,
                name=plan.name,
                provider=plan.provider,
                contract_length_months=plan.contract_length_months,
                renewable_percentage=plan.renewable_percentage,
                classifications=classifications,
                cost_at_1000_kwh=plan.cost_1000_kwh["total_monthly_usd"],
                rate_structure_summary=_summarize_rate_structure(plan.rate_structure),
                scraped_at=plan.scraped_at,
            )
            summaries.append(summary.model_dump(mode="json"))

        # Log request
        log_request(session, "search_plans", arguments, len(summaries))

    # Also log to JSONL
    log_request_to_jsonl("search_plans", arguments, len(summaries))

    result = {
        "zip_code": params.zip_code,
        "total_results": len(summaries),
        "plans": summaries,
    }

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def calculate_plan_cost_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """Calculate detailed cost breakdown for a plan.

    Args:
        arguments: Tool arguments

    Returns:
        List of TextContent with cost details
    """
    # Validate parameters
    params = CalculateParams(**arguments)

    # Query database
    with get_session() as session:
        plan = get_plan_by_id(session, params.plan_id)

        if not plan:
            result = {"error": f"Plan not found: {params.plan_id}"}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Build detailed cost response
        detail = PlanCostDetail(
            plan_id=plan.id,
            plan_name=plan.name,
            provider=plan.provider,
            cost_500_kwh=CostBreakdown(**plan.cost_500_kwh),
            cost_1000_kwh=CostBreakdown(**plan.cost_1000_kwh),
            cost_2000_kwh=CostBreakdown(**plan.cost_2000_kwh),
            rate_structure=plan.rate_structure,
            scraped_at=plan.scraped_at,
        )

        # Log request
        log_request(session, "calculate_plan_cost", arguments, 1)

    # Also log to JSONL
    log_request_to_jsonl("calculate_plan_cost", arguments, 1)

    return [TextContent(type="text", text=json.dumps(detail.model_dump(mode="json"), indent=2))]


def _summarize_rate_structure(rate_structure: Dict[str, Any]) -> str:
    """Create a human-readable summary of rate structure.

    Args:
        rate_structure: Rate structure dictionary

    Returns:
        Summary string
    """
    plan_type = rate_structure.get("plan_type", "fixed")
    base_charge = rate_structure.get("base_charge", 0)
    tiers = rate_structure.get("tiers", [])

    summary_parts = [f"{plan_type.replace('_', ' ').title()} rate"]

    if base_charge > 0:
        summary_parts.append(f"${base_charge:.2f} base charge")

    if tiers:
        # Show first tier rate
        first_tier_rate = tiers[0].get("rate_per_kwh", 0)
        summary_parts.append(f"from ${first_tier_rate:.4f}/kWh")

    return ", ".join(summary_parts)


async def main(mode="stdio", port=8080):
    """Main entry point for MCP server.
    
    Args:
        mode: "stdio" for subprocess transport, "http" for SSE/HTTP server
        port: Port number for HTTP server (default: 8080)
    """
    # Initialize database if needed
    from .db import init_database
    init_database()

    if mode == "http":
        # Run HTTP/SSE server for pre-started instances
        import uvicorn
        
        # Create SSE transport
        sse = SseServerTransport("/messages/")
        
        async def handle_sse(request: Request):
            """Handle SSE endpoint for MCP communication."""
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0],  # read_stream 
                    streams[1],  # write_stream
                    app.create_initialization_options(),
                )
            # Return empty response to avoid NoneType error
            return Response()
        
        starlette_app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse, methods=["GET"]),
                Mount("/messages/", app=sse.handle_post_message),
            ]
        )
        
        print(f"PowerToChoose MCP Server starting on http://localhost:{port}/sse", file=sys.stderr)
        print(f"Database: {init_database.__module__}", file=sys.stderr)
        
        config = uvicorn.Config(
            starlette_app,
            host="127.0.0.1",
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    else:
        # Run stdio server (default for subprocess spawning)
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )


if __name__ == "__main__":
    import asyncio
    
    # Check command line args for mode
    mode = "stdio"
    port = 8080
    if len(sys.argv) > 1:
        if sys.argv[1] == "--http":
            mode = "http"
            if len(sys.argv) > 2:
                port = int(sys.argv[2])
    
    asyncio.run(main(mode=mode, port=port))
