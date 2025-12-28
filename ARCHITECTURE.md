# PowerToChoose MCP Server - Architecture Document

**Version:** 1.0 (MVP)  
**Date:** December 27, 2025  
**Status:** Design Complete - Ready for Implementation

---

## 1. Executive Summary

The PowerToChoose MCP Server is a locally-deployed system that scrapes Texas electricity plan data from powertochoose.org, parses Electricity Facts Label (EFL) PDFs, and provides rich contextual data to LLMs via the Model Context Protocol. The MVP focuses on 7 North Texas ZIP codes with core search and cost calculation capabilities.

**Key Characteristics:**
- Fully local deployment (desktop-based for MVP)
- Containerized for portability
- 7-day rolling data cache
- Usage-based cost calculators at 3 standard tiers (500, 1000, 2000 kWh/month)

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Desktop Machine                          │
│                                                                   │
│  ┌──────────────────┐                                            │
│  │ Claude Desktop / │                                            │
│  │ VS Code          │                                            │
│  └────────┬─────────┘                                            │
│           │ stdio                                                │
│           ↓                                                      │
│  ┌──────────────────┐         ┌─────────────────────────────┐  │
│  │  MCP Server      │────────→│  Docker Container           │  │
│  │  (Native Python) │  reads  │                             │  │
│  └──────────────────┘         │  ┌─────────────────────┐    │  │
│                                │  │ Scraper Process     │    │  │
│                                │  │ (triggered by Task  │    │  │
│                                │  │  Scheduler)         │    │  │
│                                │  └─────────────────────┘    │  │
│                                │                             │  │
│  ┌──────────────────────────┐ │  ┌─────────────────────┐    │  │
│  │ Windows Task Scheduler   │─┼─→│ docker exec scraper │    │  │
│  │ (Daily 00:00)            │ │  └─────────────────────┘    │  │
│  └──────────────────────────┘ │                             │  │
│                                └─────────────────────────────┘  │
│                                          ↓                      │
│                                ┌─────────────────────────────┐  │
│                                │  Mounted Volume (./data)    │  │
│                                │                             │  │
│                                │  - powertochoose.db         │  │
│                                │  - efls/*.pdf               │  │
│                                │  - logs/*.jsonl             │  │
│                                └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Descriptions

#### MCP Server (Native Python)
- **Location:** Desktop machine (runs when Claude Desktop/VS Code invokes it)
- **Transport:** stdio (standard input/output)
- **Purpose:** Exposes search and calculation tools to LLMs
- **Database Access:** Direct file access to SQLite via mounted volume
- **Tools Exposed:**
  - `search_plans`: Search by ZIP code with optional classification filters
  - `calculate_plan_cost`: Detailed cost breakdown at 3 usage tiers

#### Docker Container (Scraper Service)
- **Base Image:** Python 3.12-slim
- **Runtime:** Continuous (keeps alive for exec commands)
- **Primary Function:** Web scraping and EFL parsing
- **Triggered By:** Windows Task Scheduler (daily at 00:00)
- **Command:** `docker exec powertochoose-scraper python -m powertochoose_mcp.scraper --today`
- **Volumes:** `./data` mounted to `/app/data` inside container

#### SQLite Database
- **Location:** `./data/powertochoose.db`
- **Mode:** WAL (Write-Ahead Logging) for safe concurrent access
- **Access Pattern:** Scraper writes, MCP server reads
- **Schema:** Managed by SQLAlchemy ORM

#### Windows Task Scheduler
- **Schedule:** Daily at 00:00 local time
- **Action:** Execute `docker exec` command to trigger scraper
- **Bucket Selection:** Determines day of week, scrapes ZIP codes where `int(zip_code) % 7 == day_of_week`

---

## 3. Data Flow

### 3.1 Scraping Flow (Daily)

```
1. Task Scheduler triggers at 00:00
   ↓
2. Determine bucket: current_day_of_week (0-6)
   ↓
3. Select ZIP codes: [z for z in ZIP_LIST if int(z) % 7 == bucket]
   ↓
4. For each ZIP code:
   a. Scrape powertochoose.org plan listings
   b. For each plan:
      - Download EFL PDF
      - Parse rate structure
      - Build cost calculator
      - Extract classifications
      - Store in database
   c. Skip problematic plans, log errors
   ↓
5. Cleanup old data:
   - Delete EFL PDFs older than 2 days
   - Delete logs older than 90 days
   ↓
6. Log scraping summary (ZIP, plan count, errors)
```

### 3.2 Query Flow (On-Demand)

```
1. User asks Claude: "Find cheap green plans in Frisco"
   ↓
2. Claude invokes MCP tool: search_plans(zip_code="75035", classifications=["green"])
   ↓
3. MCP Server queries SQLite:
   - Filter by ZIP code
   - Filter by classifications
   - Return only plans with complete calculator data
   ↓
4. MCP Server returns structured JSON to Claude
   ↓
5. User asks: "Show cost breakdown for plan X"
   ↓
6. Claude invokes: calculate_plan_cost(plan_id="X")
   ↓
7. MCP Server returns:
   - Costs at 500, 1000, 2000 kWh
   - Breakdowns: base, energy, TDU, taxes, total
   - Rate structure details
   ↓
8. Log request/response to JSONL (for classification evolution)
```

---

## 4. Technology Stack

### 4.1 Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Programming Language | Python | 3.12 | Core application logic |
| MCP SDK | `mcp` | Latest | Model Context Protocol server |
| Database | SQLite | 3.x | Plan and log storage |
| ORM | SQLAlchemy | 2.x | Database abstraction |
| Validation | Pydantic | 2.x | Data models and validation |
| HTTP Client | httpx | Latest | Async web scraping |
| HTML Parser | BeautifulSoup4 | Latest | Plan listing parsing |
| PDF Parser | pypdf / pdfplumber | Latest | EFL text extraction |
| Containerization | Docker + Docker Compose | Latest | Deployment packaging |
| Scheduling | Windows Task Scheduler | Built-in | Daily scraping trigger |

### 4.2 Python Package Dependencies

```txt
mcp>=1.0.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
pypdf>=4.0.0
pydantic>=2.5.0
sqlalchemy>=2.0.0
```

---

## 5. Database Schema

### 5.1 Core Tables

```sql
-- Plans table
CREATE TABLE plans (
    id TEXT PRIMARY KEY,                    -- Unique plan identifier
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    contract_length_months INTEGER,
    renewable_percentage INTEGER,
    cancellation_fee DECIMAL,
    
    -- Calculator data (JSON)
    rate_structure JSON NOT NULL,          -- Parsed EFL rate details
    cost_500_kwh JSON NOT NULL,            -- Full breakdown at 500 kWh
    cost_1000_kwh JSON NOT NULL,           -- Full breakdown at 1000 kWh
    cost_2000_kwh JSON NOT NULL,           -- Full breakdown at 2000 kWh
    
    -- Metadata
    scraped_at TIMESTAMP NOT NULL,
    efl_url TEXT,
    plan_url TEXT,
    
    -- Indexes
    INDEX idx_zip_code (zip_code),
    INDEX idx_scraped_at (scraped_at)
);

-- Plan classifications (many-to-many)
CREATE TABLE plan_classifications (
    id INTEGER PRIMARY KEY,
    plan_id TEXT NOT NULL,
    classification TEXT NOT NULL,          -- "green", "ev", "time_of_use", etc.
    source TEXT NOT NULL,                  -- "website" or "derived"
    
    FOREIGN KEY (plan_id) REFERENCES plans(id),
    UNIQUE(plan_id, classification)
);

-- Request logs (for classification evolution)
CREATE TABLE request_logs (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    tool_name TEXT NOT NULL,
    parameters JSON NOT NULL,
    result_count INTEGER,
    classifications_used JSON,
    
    INDEX idx_timestamp (timestamp)
);
```

### 5.2 Cost Breakdown JSON Structure

```json
{
    "usage_kwh": 1000,
    "base_charge_usd": 9.95,
    "energy_charge_usd": 85.00,
    "energy_rate_per_kwh": 0.085,
    "tdu_delivery_usd": 42.50,
    "taxes_fees_usd": 13.75,
    "total_monthly_usd": 151.20,
    "breakdown_by_tier": [
        {"tier": "0-500", "kwh": 500, "rate": 0.090, "cost": 45.00},
        {"tier": "500+", "kwh": 500, "rate": 0.080, "cost": 40.00}
    ]
}
```

---

## 6. File Structure

```
c:\code\powertochoose-mcp\
├── .github\
│   └── copilot-instructions.md          # AI agent guidance
├── data\                                 # Docker volume mount (gitignored)
│   ├── powertochoose.db                 # SQLite database
│   ├── efls\                            # EFL PDFs (2-day retention)
│   │   └── {plan_id}_{date}.pdf
│   └── logs\                            # Request logs (90-day retention)
│       └── requests_{YYYY-MM-DD}.jsonl
├── src\
│   └── powertochoose_mcp\
│       ├── __init__.py
│       ├── __main__.py                  # MCP server entry point
│       ├── server.py                    # MCP tool definitions
│       ├── scraper.py                   # Web scraper + CLI
│       ├── efl_parser.py                # PDF parsing logic
│       ├── calculator.py                # Cost calculation
│       ├── models.py                    # Pydantic models
│       ├── config.py                    # Configuration (ZIP codes, paths)
│       ├── db\
│       │   ├── __init__.py
│       │   ├── schema.py                # SQLAlchemy models
│       │   ├── operations.py            # Database queries
│       │   └── cleanup.py               # Data retention logic
│       └── utils\
│           ├── __init__.py
│           └── logging.py               # Request logging
├── tests\
│   └── integration\
│       ├── test_scraper.py
│       ├── test_efl_parser.py
│       └── test_mcp_tools.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── ARCHITECTURE.md                      # This document
└── README.md
```

---

## 7. Configuration

### 7.1 Initial ZIP Codes (North Texas)

```python
# config.py
ZIP_CODES = [
    "75035",  # Frisco
    "75024",  # Plano (west)
    "75074",  # Plano (east)
    "75093",  # Plano (north)
    "75034",  # Frisco (north)
    "75033",  # Frisco (south)
    "75070",  # McKinney
]

# Bucket assignment: int(zip_code) % 7
# 75035 % 7 = 0 (Sunday)
# 75024 % 7 = 3 (Wednesday)
# etc.
```

### 7.2 Docker Compose Configuration

```yaml
version: '3.8'

services:
  scraper:
    build: .
    container_name: powertochoose-scraper
    command: tail -f /dev/null  # Keep alive
    volumes:
      - ./data:/app/data
      - ./src:/app/src
    environment:
      - DATABASE_PATH=/app/data/powertochoose.db
      - EFL_DIR=/app/data/efls
      - LOG_DIR=/app/data/logs
    restart: unless-stopped
```

### 7.3 MCP Server Configuration (Claude Desktop)

```json
{
  "mcpServers": {
    "powertochoose": {
      "command": "python",
      "args": ["-m", "powertochoose_mcp"],
      "cwd": "c:\\code\\powertochoose-mcp",
      "env": {
        "DATABASE_PATH": "c:\\code\\powertochoose-mcp\\data\\powertochoose.db"
      }
    }
  }
}
```

### 7.4 Windows Task Scheduler

**Task Name:** PowerToChoose Daily Scraper  
**Trigger:** Daily at 00:00  
**Action:** Start a program
- **Program:** `docker`
- **Arguments:** `exec powertochoose-scraper python -m powertochoose_mcp.scraper --today`
- **Start in:** `c:\code\powertochoose-mcp`

---

## 8. Key Design Decisions

### 8.1 Why SQLite?
- ✅ Single-file database (easy backup/migration)
- ✅ No separate database server needed
- ✅ Sufficient for ~500 plans × 7 ZIP codes
- ✅ WAL mode handles concurrent reads safely
- ✅ SQLAlchemy allows easy migration to PostgreSQL later

### 8.2 Why Docker Compose?
- ✅ Portable across machines (desktop → NAS → cloud)
- ✅ Consistent environment
- ✅ Easy volume management
- ✅ Can add services later (PostgreSQL, Redis, etc.)
- ✅ No conflicts with host Python environment

### 8.3 Why External Scheduling (Task Scheduler)?
- ✅ Container can be lightweight (no cron daemon)
- ✅ Clear separation of concerns
- ✅ Easier to debug (Windows task history)
- ✅ Can manually trigger: `docker exec powertochoose-scraper python -m powertochoose_mcp.scraper --all`

### 8.4 Why 7 Buckets?
- ✅ Balances freshness (7-day max age) with scraping load
- ✅ Simple modulo arithmetic for assignment
- ✅ One scrape per day = ~10-15 min runtime
- ✅ Reduces load on powertochoose.org
- ✅ Easy to adjust (add/remove ZIP codes without rebalancing)

### 8.5 Why JSONL for Logs?
- ✅ Easy to append (no parsing entire file)
- ✅ Streaming-friendly for future analysis
- ✅ Human-readable for debugging
- ✅ No schema migrations needed
- ✅ Standard format with tooling support

---

## 9. Error Handling Strategy

### 9.1 Scraping Failures
- Skip problematic plan, log error to JSONL
- Continue processing remaining plans
- Summary at end: total plans, successful parses, failures

### 9.2 EFL Parsing Failures
- Mark plan as incomplete in database (flag: `efl_parsed = false`)
- Exclude from search results
- Retry on next scrape (7 days later)

### 9.3 Unsupported ZIP Codes
- Return friendly message: "Service coming to your ZIP code soon"
- Log query for future expansion planning

### 9.4 Database Errors
- Log error details
- Return user-friendly message via MCP
- Don't expose internal stack traces

---

## 10. Data Retention Policies

| Data Type | Retention | Cleanup Method |
|-----------|-----------|----------------|
| Plan data | 7 days (rolling) | Overwrite on re-scrape |
| EFL PDFs | 2 days | Delete files older than 2 days at scrape start |
| Request logs | 90 days | Delete JSONL files older than 90 days at scrape start |
| Database logs | 90 days | Delete rows older than 90 days at scrape start |

---

## 11. Testing Strategy (MVP)

### 11.1 Integration Tests

```python
# tests/integration/test_scraper.py
def test_scrape_one_zip():
    """Test scraping a single ZIP code end-to-end."""
    result = scrape_zip_code("75035")
    assert len(result) > 0
    assert all(plan.calculator_complete for plan in result)

# tests/integration/test_efl_parser.py
def test_parse_sample_efl():
    """Test EFL PDF parsing with known sample."""
    efl = parse_efl("sample_efl.pdf")
    assert efl.rate_structure is not None
    assert len(efl.usage_tiers) == 3

# tests/integration/test_mcp_tools.py
def test_search_plans_tool():
    """Test MCP search_plans tool."""
    result = search_plans(zip_code="75035")
    assert isinstance(result, list)
    assert all("calculator" in plan for plan in result)
```

---

## 12. Future Enhancements (Post-MVP)

1. **Comparison Tool**: Side-by-side plan comparison
2. **Recommendation Engine**: LLM-guided best plan selection
3. **More ZIP Codes**: Expand to Dallas, Houston, Austin
4. **Time-of-Use Analysis**: Parse and compare time-based pricing
5. **Provider Ratings**: Scrape/integrate customer reviews
6. **Cost Alerts**: Notify when better plans become available
7. **Export Tools**: Generate comparison reports (PDF, Excel)
8. **Admin Dashboard**: Web UI for monitoring scraper health
9. **PostgreSQL Migration**: If scaling beyond ~10,000 plans
10. **Cloud Deployment**: Move to NAS or Oracle Cloud for remote access

---

## 13. Migration Path to NAS

When ready to move from desktop to Synology NAS:

1. **Copy Project Files**: 
   - `rsync` or manual copy to NAS shared folder
   
2. **Install Docker on NAS**:
   - Enable Docker package from Package Center
   
3. **Update docker-compose.yml**:
   - Change volume paths to NAS paths
   
4. **Synology Task Scheduler**:
   - Replace Windows Task Scheduler with Synology's built-in scheduler
   - Script: `/volume1/scripts/run_scraper.sh`
   
5. **MCP Server Connection**:
   - Option A: Mount NAS volume on desktop via SMB
   - Option B: Install Tailscale for remote access

---

## 14. Security Considerations

- ✅ No authentication needed (public data source)
- ✅ No sensitive data stored (plan pricing is public)
- ✅ SQLite file permissions: Read/write for user only
- ✅ No exposed ports (MCP uses stdio)
- ⚠️ Future: If exposing to internet, add authentication layer
- ⚠️ Rate limiting: Respect powertochoose.org (delays between requests)

---

## 15. Performance Estimates

| Operation | Expected Duration | Notes |
|-----------|-------------------|-------|
| Scrape 1 ZIP code | ~5-10 minutes | ~50-100 plans, depends on EFL download speed |
| Parse 1 EFL PDF | ~2-5 seconds | Depends on PDF complexity |
| MCP query (search) | <100ms | Direct SQLite query, indexed |
| MCP query (calculate) | <50ms | In-memory calculation from stored data |
| Daily scrape (1 bucket) | ~10-15 minutes | 1-2 ZIP codes per bucket |
| Database size | ~50-100 MB | ~500 plans with full rate data |
| EFL storage (2 days) | ~500 MB | ~100 PDFs × 5MB average |

---

## 16. Success Criteria (MVP)

- ✅ Successfully scrape 7 ZIP codes across 7 days
- ✅ Parse >90% of EFL PDFs successfully
- ✅ Return accurate cost calculations for all 3 usage tiers
- ✅ MCP tools respond in <500ms
- ✅ Zero manual intervention required for daily scraping
- ✅ Integration tests pass
- ✅ Docker container runs stably for 7+ days
- ✅ Data retention policies execute correctly

---

## 17. Support & Maintenance

**Initial Setup Time:** 2-3 hours  
**Ongoing Maintenance:** <15 minutes/week  
**Monitoring:** Check Task Scheduler history weekly

**Common Issues:**
- Scraper failures → Check logs in `data/logs/`
- Database locked → Verify WAL mode enabled
- Missing data → Check Task Scheduler ran successfully
- Container stopped → `docker-compose up -d` to restart

---

**Document Version:** 1.0  
**Last Updated:** December 27, 2025  
**Next Review:** After MVP implementation complete
