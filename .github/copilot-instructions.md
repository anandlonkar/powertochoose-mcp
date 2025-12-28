# PowerToChoose MCP Server - AI Agent Instructions

## ⚠️ CRITICAL: Project Boundary Rule
**NEVER make changes outside of `c:\code\powertochoose-mcp\` without explicit user confirmation.**
- Do not modify system files, global configs, or other projects
- All changes must be contained within this repository
- If a task requires external changes, ask for permission first

## Project Overview
MCP (Model Context Protocol) server for scraping and analyzing electricity plans from powertochoose.org, a Texas electricity retail shopping comparison site. The server extracts plan data, parses EFL (Electricity Facts Label) PDFs, and creates usage-based calculators to provide rich context for LLM-based plan recommendations.

**MVP Scope**: Core search and cost calculation tools for 7 North Texas ZIP codes around Frisco (75035).

**📖 See [ARCHITECTURE.md](../ARCHITECTURE.md) for complete system design, deployment architecture, and technical decisions.**

## Architecture

### Deployment Model (MVP)
- **Location**: Desktop machine (portable to NAS later)
- **Container**: Docker Compose with scraper service
- **Database**: SQLite with WAL mode (mounted volume)
- **Scheduling**: Windows Task Scheduler triggers daily scrape via `docker exec`
- **MCP Server**: Native Python (invoked by Claude Desktop via stdio)

### Core Components
- **MCP Server**: Python-based server implementing stdio transport for Claude Desktop/VS Code
- **Web Scraper**: Scrapes powertochoose.org for plan listings by ZIP code (runs in Docker)
- **Scheduled Scraper**: Daily task (00:00 local time) using ZIP code modulo 7 for bucket assignment
- **EFL Parser**: Downloads and parses EFL PDFs to extract rate structures
- **Cost Calculator**: Computes costs at three usage tiers (500, 1000, 2000 kWh/month)
- **SQLite Database**: Stores plan data, classifications, parsed EFLs (7-day rolling cache)
- **Request Logger**: Logs LLM queries and responses to JSONL files (90-day retention)
- **File Manager**: Stores EFL PDFs locally for 2 days, then discards

### Key Data Entities
- **Electricity Plans**: Rate structures, contract terms, pricing, classifications (green, EV, time-of-use)
- **Providers**: Retail Electric Provider (REP) information
- **Service Areas**: TDU regions and supported ZIP codes
- **Cost Breakdowns**: Base charge, energy charge by tier, TDU delivery, taxes, total
- **Plan Classifications**: Website tags (renewable %, EV-friendly, etc.) - evolves based on LLM usage

## Development Workflows

### Setup
```bash
# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Initialize database
python -m powertochoose_mcp.db.init

# Run initial scrape for all buckets (optional, for testing)
python -m powertochoose_mcp.scraper --all

# Run MCP server (stdio transport)
python -m powertochoose_mcp
```

### Scheduled Scraping
```powershell
# Set up Windows Task Scheduler for daily 00:00 run
# Task runs: python -m powertochoose_mcp.scraper --today
# Determines bucket from current day of week, scrapes assigned ZIP codes
```

### Testing with MCP Inspector
```bash
# Install MCP inspector globally
npm install -g @modelcontextprotocol/inspector

# Test the server
mcp-inspector python -m powertochoose_mcp
```

### Integration Tests
```bash
# Run end-to-end tests (scrape → parse → store → query)
python -m pytest tests/integration/
```

## Project Conventions

### MCP Server Implementation
- Use `mcp` Python package for server implementation
- Implement stdio transport for VS Code/Claude Desktop integration
- Define tools with clear JSON schemas for parameters
- Return structured data (avoid plain text responses)

### Scraping Patterns
```python
# Example scraper structure
async def scrape_zip_code(zip_code: str) -> list[PlanData]:
    """Scrape all plans for a ZIP code from powertochoose.org."""
    # Fetch plan listing page
    # Parse HTML for plan cards
    # For each plan, download and parse EFL PDF
    # Extract rate structure and build calculator
    # Store in database with classifications
```

### Data Validation
- Use Pydantic models for all tool parameters and database entities
- Validate ZIP codes (5-digit format, must be in configured list)
- Usage tiers fixed at 500, 1000, 2000 kWh/month
- Log all validation errors

### Error Handling
- **Scraping failures**: Skip problematic plans, log error, continue processing
- **EFL parsing failures**: Mark plan as incomplete, exclude from search results
- **Unsupported ZIP codes**: Return message "Service coming to your ZIP code soon"
- **Database errors**: Log and fail gracefully with user-friendly messages
- Return only plans with complete calculator data in search results

### Data Retention
- **Plan data**: 7-day rolling cache (refreshed via daily bucket scraping)
- API at `http://api.powertochoose.org/` exists but lacks plan details
- **Scraping Strategy**: HTML parsing of plan listings, download EFL PDFs from plan pages
- **EFL Documents**: PDF files with rate structures, tiered pricing, fees
- No authentication required (public data)
- **Rate Limiting**: Respect site limits, use delays between requests
- **Initial ZIP Codes**: 7 codes around Frisco, TX (75035 area)
- **Bucket Assignment**: `int(zip_code) % 7` determines day of week for scraping

### Required Python Packages
- `mcp`: MCP server SDK (stdio transport)
- `httpx`: Async HTTP client for scraping
- `beautifulsoup4`: HTML parsing
- `pypdf` or `pdfplumber`: EFL PDF text extraction
- `pydantic`: Data models and validation
- `sqlalchemy`: SQLite ORM for plan storage
- `schedule` or Windows Task Scheduler: Daily scraping at 00:00eters
- Validate ZIP codes (5-digit Texas ZIP codes only)
- Validate usage values (typical range: 500-3000 kWh/month)
- Handle API rate limiting and errors gracefully

### Error Handling
- Wrap API calls with proper exception handling
- Return user-friendly error messages through MCP protocol
- Log errors for debugging but don't expose internal details to MCP clients

## External Dependencies

### PowerToChoose.org Website
- Base URL: `http://www.powertochoose.org/`
- Sparse API at `http://api.powertochoose.org/` (not sufficient for plan details)
- **Scraping Strategy**: HTML parsing of plan listings and individual plan pages
- **EFL Documents**: PDF files containing rate structure details (requires PDF parsing)
- No authentication required (public data)
- Respect rate limits and implement caching (plans change frequently)

### Required Python Packages
- `mcp`: MCP server SDK
- `httpx` or `aiohttp`: Async HTTP client for scraping
- `beautifulsoup4` or `playwright`: HTML parsing and scraping
- `pypdf2` or `pdfplumber`: EFL PDF parsing
- `pydantic`: Data validation and serialization
- `sqlite3` or `sqlalchemy`: Local cache for scraped plans
crape_plans_by_zip**: Scrape and cache plans for a North Texas ZIP code
2. **parse_plan_efl**: Extract EFL PDF and build usage calculator for a specific plan
3. **calculate_plan_cost**: Calculate actual cost for a plan given usage pattern (500, 1000, 2000 kWh tiers)
4. **compare_plans_for_usage**: Compare multiple plans for specific customer usage with recommendations
5. **get_best_plan**: LLM-driven recommendation based on usage profile and preferences

### Tool Design Principles
- Return structured data with calculator details for LLM consumption
- Include full rate breakdowns (base charges, energy charges per tier, TDU delivery)
- Cache scraped data to avoid excessive scraping
- Provide confidence scores for recommendations based on data freshnes
- Clear, descriptive tool names and descriptions
- Required vs optional parameters clearly defined
- Return consistent data structures
- Include units ($/kWh, months, kWh) in field names

## Testing Strategy (MVP)

### Integration Tests
- **Scraper**: Test scraping one ZIP code, verify plan data stored in DB
- **EFL Parser**: Test downloading and parsing sample EFL PDFs
- **Calculator**: Verify cost calculations match EFL rate structures
- **MCP Tools**: Test search_plans and calculate_plan_cost end-to-end
- **Data Retention**: Verify 2-day EFL cleanup, 7-day plan cache, 90-day logs

### Deferred to Phase 2
- Unit tests for individual components
- LLM query testing with Claude Desktop
- Performance/load testing

## Configuration

### MCP Server Registration
Add to Claude Desktop or VS Code MCP settings:
```json
{
  "mcpServers": {
    "powertochoose": {
      "command": "python",
      "args": ["-m", "powertochoose_mcp"],
      "cwd": "c:\\code\\powertochoose-mcp"
    }
  }
}
```

## Key Files to Create
- `src/powertochoose_mcp/__main__.py`: MCP server entry point (stdio transport)
- `src/powertochoose_mcp/server.py`: MCP tool definitions (search_plans, calculate_plan_cost)
- `src/powertochoose_mcp/scraper.py`: Web scraper and scheduled task entry point
- `src/powertochoose_mcp/efl_parser.py`: PDF parsing and rate structure extraction
- `src/powertochoose_mcp/calculator.py`: Cost calculation logic for three usage tiers
- `src/powertochoose_mcp/models.py`: Pydantic models for plans, rates, costs
- `src/powertochoose_mcp/db/schema.py`: SQLAlchemy models for plans, classifications, logs
- `src/powertochoose_mcp/db/init.py`: Database initialization
- `src/powertochoose_mcp/config.py`: ZIP code list, bucket assignments, paths
- `tests/integration/`: End-to-end test suite
- `pyproject.toml`: Package configuration
