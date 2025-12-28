# FastAPI Backend - Quick Start Guide

## Local Development Setup

### 1. Install Dependencies
```bash
cd c:\code\powertochoose-mcp
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Set Up Environment Variables
```bash
# Copy example file
cp .env.example .env

# Edit .env and add your Gemini API key
# Get one at: https://aistudio.google.com/app/apikey
notepad .env
```

### 3. Start the MCP Server (Terminal 1)
```bash
cd c:\code\powertochoose-mcp
.\.venv\Scripts\Activate.ps1
python -m powertochoose_mcp.server --http 8080
```

### 4. Start the API Server (Terminal 2)
```bash
cd c:\code\powertochoose-mcp
.\.venv\Scripts\Activate.ps1

# Load environment variables (PowerShell)
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

# Start API server
python -m powertochoose_mcp.api_server
```

### 5. Test the API
```bash
# In Terminal 3
cd c:\code\powertochoose-mcp
.\.venv\Scripts\Activate.ps1
python test_api.py
```

### 6. Open API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/api/health

---

## Docker Development

### Build and Run with Docker Compose
```bash
cd c:\code\powertochoose-mcp

# Make sure .env file exists with GEMINI_API_KEY
# Docker Compose will automatically load it

# Build containers
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Test
curl http://localhost:8000/api/health
```

### Individual Container Commands
```bash
# Start MCP server only
docker-compose up -d mcp-server

# Start API server only  
docker-compose up -d api-server

# Stop all
docker-compose down

# Rebuild after code changes
docker-compose build api-server
docker-compose up -d api-server
```

---

## API Endpoints

### 1. Root - Service Info
```bash
curl http://localhost:8000/
```

### 2. Health Check
```bash
curl http://localhost:8000/api/health
```

### 3. Browse Plans
```bash
curl http://localhost:8000/api/plans/75074
```

### 4. Analyze CSV (Upload)
```bash
# Create sample CSV first
curl -X POST "http://localhost:8000/api/analyze" \
  -F "csv_file=@sample-meter-data.csv" \
  -F "zip_code=75074"
```

---

## Testing with Sample Data

### Create Sample CSV
Create `sample-meter-data.csv`:
```csv
Date,Usage,Reading Type,ESIID
2024-01-01,15.2,Actual,12345678901234567
2024-01-02,18.5,Actual,12345678901234567
2024-01-03,14.8,Actual,12345678901234567
2024-01-04,19.3,Actual,12345678901234567
2024-01-05,17.6,Actual,12345678901234567
```

### Test Upload
```powershell
# PowerShell
$file = Get-Content -Path "sample-meter-data.csv" -Raw
Invoke-RestMethod -Uri "http://localhost:8000/api/analyze" `
  -Method Post `
  -Form @{
    csv_file = Get-Item "sample-meter-data.csv"
    zip_code = "75074"
  }
```

---

## Rate Limits

- **Anonymous users**: 10 requests/hour for `/api/analyze`
- **Anonymous users**: 30 requests/hour for `/api/plans/*`
- Rate limit based on IP address

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key (required) | None |
| `MCP_SERVER_URL` | MCP server endpoint | http://localhost:8080/sse |
| `ALLOWED_ORIGINS` | CORS allowed origins | https://dijit.tech,http://localhost:3000 |
| `DATABASE_PATH` | SQLite database path | /app/data/powertochoose.db |

---

## Troubleshooting

### Agent Not Initialized
```
Error: "Agent not initialized - check GEMINI_API_KEY"
```
**Solution**: Make sure `GEMINI_API_KEY` is set in `.env` file

### MCP Server Connection Failed
```
Error: "mcp_server": false in /api/health
```
**Solution**: Start MCP server first: `python -m powertochoose_mcp.server --http 8080`

### Port Already in Use
```
Error: Address already in use
```
**Solution**: 
```bash
# Find process using port 8000
netstat -ano | findstr :8000
# Kill process (replace PID)
taskkill /PID <PID> /F
```

### Database Not Found
```
Error: "no such table: plans"
```
**Solution**: Initialize database first:
```bash
python -m powertochoose_mcp.db.init
```

---

## Next Steps

1. ✅ **Local testing complete** - API server working
2. ⏳ **Deploy to Synology** - Follow SYNOLOGY_DEPLOYMENT.md
3. ⏳ **Set up Cloudflare Tunnel** - Expose API to internet
4. ⏳ **Build frontend** - Create React UI on dijit.tech
5. ⏳ **Production testing** - End-to-end validation

---

## Directory Structure

```
c:\code\powertochoose-mcp\
├── src/
│   └── powertochoose_mcp/
│       ├── api_server.py          # ← FastAPI server
│       ├── server.py               # MCP server
│       └── db/
│           └── operations.py       # Database queries
├── Dockerfile                      # MCP server container
├── Dockerfile.api                  # API server container
├── docker-compose.yml              # Multi-container setup
├── .env.example                    # Environment template
├── .env                            # Your actual config (gitignored)
├── test_api.py                     # Test script
└── requirements.txt                # Python dependencies
```

---

**Last Updated**: December 28, 2025
