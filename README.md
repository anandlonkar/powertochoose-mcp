# PowerToChoose MCP Server

MCP (Model Context Protocol) server for scraping and analyzing Texas electricity plans from powertochoose.org. Provides rich contextual data to LLMs for intelligent plan recommendations.

## Features

- **Web Scraping**: Automated scraping of electricity plans from powertochoose.org
- **EFL Parsing**: Extracts rate structures from Electricity Facts Label PDFs
- **Cost Calculator**: Computes costs at 500, 1000, and 2000 kWh usage tiers
- **MCP Integration**: Exposes search and calculation tools to Claude Desktop/VS Code
- **Local Deployment**: Fully containerized with Docker Compose
- **Data Retention**: 7-day plan cache, 2-day EFL storage, 90-day request logs

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/anandlonkar/powertochoose-mcp.git
cd powertochoose-mcp

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Initialize database
python -c "from powertochoose_mcp.db import init_database; init_database()"
```

### Run with Docker

```bash
# Build and start container
docker-compose up -d

# Initialize database (first time only)
docker exec powertochoose-scraper python -c "from powertochoose_mcp.db import init_database; init_database()"

# Run scraper manually
docker exec powertochoose-scraper python -m powertochoose_mcp.scraper --all
```

### Configure Claude Desktop

Add to `claude_desktop_config.json`:

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

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design, deployment model, and technical decisions.

## Available MCP Tools

### 1. search_plans

Search electricity plans by ZIP code with optional filters.

```python
{
  "zip_code": "75035",
  "classifications": ["green", "ev"],  # optional
  "max_results": 10  # optional
}
```

### 2. calculate_plan_cost

Get detailed cost breakdown for a specific plan at all usage tiers.

```python
{
  "plan_id": "abc123def456"
}
```

## Testing

```bash
# Run integration tests
pytest tests/integration/ -v
```

## Initial Coverage

**North Texas ZIP Codes (MVP)**:
- 75035 (Frisco)
- 75024 (Plano West)
- 75074 (Plano East)
- 75093 (Plano North)
- 75034 (Frisco North)
- 75033 (Frisco South)
- 75070 (McKinney)

## Scheduled Scraping

Set up Windows Task Scheduler:
- **Schedule**: Daily at 00:00
- **Command**: `docker exec powertochoose-scraper python -m powertochoose_mcp.scraper --today`
- **Working Directory**: `c:\code\powertochoose-mcp`

## Project Structure

```
src/powertochoose_mcp/
├── __init__.py
├── __main__.py          # MCP server entry point
├── server.py            # MCP tool definitions
├── scraper.py           # Web scraper
├── efl_parser.py        # PDF parsing
├── calculator.py        # Cost calculation
├── models.py            # Pydantic models
├── config.py            # Configuration
├── db/                  # Database layer
│   ├── schema.py
│   ├── operations.py
│   └── __init__.py
└── utils/               # Utilities
    ├── logging.py
    └── __init__.py
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read ARCHITECTURE.md first to understand the system design.

## Support

For issues or questions, please open a GitHub issue.
