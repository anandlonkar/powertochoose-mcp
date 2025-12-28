# PowerToChoose Public API - Architecture for dijit.tech

**Version:** 1.0  
**Target:** Public web service at dijit.tech  
**Platform:** Synology DS920+ + Cloud  
**Date:** December 28, 2025

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         dijit.tech                               │
│                     (Public Web Frontend)                        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  React/Next.js Web UI                                     │  │
│  │  - Upload CSV interface                                   │  │
│  │  - Plan recommendation display                            │  │
│  │  - Cost comparison charts                                 │  │
│  └────────────┬─────────────────────────────────────────────┘  │
│               │ HTTPS/API                                       │
└───────────────┼─────────────────────────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────────────────────────┐
│              API Gateway / Reverse Proxy                         │
│              (Cloudflare Tunnel or Nginx)                        │
│                                                                   │
│  ├─ Rate Limiting (100 req/hour per IP)                         │
│  ├─ Authentication (API keys for registered users)              │
│  ├─ SSL/TLS termination                                          │
│  └─ CORS configuration                                           │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Synology DS920+ (Your NAS)                     │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Server (Port 8000)                              │  │
│  │  - POST /api/analyze (CSV upload endpoint)               │  │
│  │  - POST /api/recommend (plan recommendation)             │  │
│  │  - GET /api/plans/{zip_code} (browse plans)              │  │
│  └────────────┬─────────────────────────────────────────────┘  │
│               │                                                  │
│               ↓                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MCP Server (Port 8080) - Internal Only                  │  │
│  │  - search_plans tool                                     │  │
│  │  - calculate_plan_cost tool                              │  │
│  └────────────┬─────────────────────────────────────────────┘  │
│               │                                                  │
│               ↓                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Google ADK Agent (In FastAPI)                           │  │
│  │  - Meter data analyzer                                   │  │
│  │  - Plan recommendation logic                             │  │
│  │  - Cost comparison                                       │  │
│  └────────────┬─────────────────────────────────────────────┘  │
│               │                                                  │
│               ↓                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SQLite Database + File Storage                          │  │
│  │  - Electricity plans (163+ plans, 7-day cache)           │  │
│  │  - User uploads (temporary, 1-hour retention)            │  │
│  │  - API usage logs (rate limiting)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown

### 2.1 Public Web Frontend (dijit.tech)

**Technology Stack:**
- Next.js 14+ (React framework)
- TypeScript
- Tailwind CSS (styling)
- Vercel deployment (free tier)

**Features:**
1. **CSV Upload Interface**
   - Drag-and-drop file upload
   - Sample CSV download
   - Format validation (client-side)
   - File size limit: 10MB

2. **Plan Recommendations Display**
   - Top 3 recommended plans
   - Cost comparison table (500/1000/2000 kWh)
   - Interactive charts (usage patterns)
   - Detailed cost breakdown

3. **User Experience**
   - No account required (anonymous usage)
   - Optional: Email for results
   - Privacy notice (CSV deleted after 1 hour)
   - Usage limits displayed (100 requests/hour)

**Example UI Flow:**
```
1. User lands on dijit.tech/power-plan-finder
2. Uploads CSV (ESIID meter data format)
3. Click "Find Best Plans"
4. Loading state (agent analyzing...)
5. Results page:
   - Recommended plans
   - Cost comparison
   - Download report (PDF)
```

### 2.2 API Gateway / Reverse Proxy

**Option A: Cloudflare Tunnel (Recommended)**
- No port forwarding required
- Free tier available
- Built-in DDoS protection
- Automatic HTTPS
- Setup: `cloudflared tunnel create powertochoose`

**Option B: Nginx on Synology**
- Control Panel → Login Portal → Advanced → Reverse Proxy
- Source: `api.dijit.tech:443` → Destination: `localhost:8000`
- Requires: Domain DNS → NAS IP, port forwarding 443

**Security Layers:**
- Rate limiting: 100 requests/hour per IP
- API key validation for premium features
- CORS: Only dijit.tech allowed
- Request size limit: 10MB
- Content-Type validation

### 2.3 FastAPI Backend (New Component)

**Purpose:** Public API that wraps MCP server and ADK agent

**File:** `src/powertochoose_mcp/api_server.py`

**Endpoints:**

1. **POST /api/analyze**
   ```json
   Request:
   {
     "csv_data": "base64_encoded_csv",
     "zip_code": "75074"
   }
   
   Response:
   {
     "status": "success",
     "recommendations": [
       {
         "plan_name": "Sustainable Days Bundle - 3",
         "provider": "JUST ENERGY",
         "monthly_cost": 24.04,
         "renewable_percentage": 31,
         "contract_months": 3,
         "breakdown": {...}
       }
     ],
     "usage_analysis": {
       "avg_monthly_kwh": 164.4,
       "peak_time": "20:00",
       "pattern_type": "time_of_use"
     }
   }
   ```

2. **GET /api/plans/{zip_code}**
   - Browse available plans
   - Optional filters: ?renewable=true&max_months=6

3. **GET /api/health**
   - Server health check
   - Database status
   - Last scrape timestamp

**Authentication:**
```python
# API Key in header
headers = {
    "X-API-Key": "your_api_key_here"  # Optional for rate limiting bypass
}
```

**Rate Limiting:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/analyze")
@limiter.limit("10/hour")  # 10 requests per hour per IP
async def analyze_csv(request: Request):
    ...
```

### 2.4 MCP Server (Internal Only)

**No Changes Required**
- Runs on port 8080 (localhost only)
- Not exposed to internet
- FastAPI server connects internally via SSE

### 2.5 Google ADK Agent Integration

**Embedded in FastAPI:**
```python
from google import genai
from google.adk import agents, tools
from google.adk.tools.mcp_tool import McpToolset

# Initialize ADK agent within FastAPI
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

powertochoose_toolset = McpToolset(
    connection_params=SseConnectionParams(
        url="http://localhost:8080/sse"
    )
)

search_agent = agents.create(
    name="search_agent",
    model="gemini-2.0-flash",
    instruction="You are a specialist...",
    toolsets=[powertochoose_toolset]
)

# Use in API endpoint
result = await search_agent.generate(
    prompt=f"Find best plan for {usage_pattern} in {zip_code}"
)
```

---

## 3. Deployment Architecture

### 3.1 Synology DS920+ Setup

**Docker Compose (Updated):**
```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    container_name: powertochoose-mcp
    command: python -m powertochoose_mcp.server --http 8080
    ports:
      - "127.0.0.1:8080:8080"  # Localhost only
    volumes:
      - /volume1/docker/powertochoose-mcp/data:/app/data
    restart: always
    networks:
      - internal

  api-server:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: powertochoose-api
    command: uvicorn powertochoose_mcp.api_server:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"  # Exposed to internet (via reverse proxy)
    volumes:
      - /volume1/docker/powertochoose-mcp/data:/app/data
      - /volume1/docker/powertochoose-mcp/uploads:/app/uploads
    environment:
      - MCP_SERVER_URL=http://mcp-server:8080/sse
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - ALLOWED_ORIGINS=https://dijit.tech
    restart: always
    networks:
      - internal
      - external
    depends_on:
      - mcp-server

networks:
  internal:
    driver: bridge
  external:
    driver: bridge
```

### 3.2 Cloudflare Tunnel Setup

**Install on Synology:**
```bash
# SSH to NAS
ssh admin@your-nas-ip

# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
sudo chmod +x /usr/local/bin/cloudflared

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create powertochoose

# Configure tunnel
cat > /volume1/docker/powertochoose-mcp/cloudflared-config.yml <<EOF
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: api.dijit.tech
    service: http://localhost:8000
  - service: http_status:404
EOF

# Run tunnel
cloudflared tunnel --config /volume1/docker/powertochoose-mcp/cloudflared-config.yml run powertochoose
```

**DNS Setup:**
- Cloudflare DNS: `api.dijit.tech` → CNAME to `<TUNNEL_ID>.cfargotunnel.com`

### 3.3 Frontend Deployment (Vercel)

**Repository Structure:**
```
dijit.tech/
├── pages/
│   └── power-plan-finder.tsx
├── components/
│   ├── CSVUploader.tsx
│   ├── PlanRecommendations.tsx
│   └── CostComparison.tsx
├── lib/
│   └── api.ts  # API client
└── public/
    └── sample-meter-data.csv
```

**API Client:**
```typescript
// lib/api.ts
export async function analyzeMeterData(csvFile: File, zipCode: string) {
  const formData = new FormData();
  formData.append('csv_file', csvFile);
  formData.append('zip_code', zipCode);

  const response = await fetch('https://api.dijit.tech/api/analyze', {
    method: 'POST',
    body: formData,
  });

  return response.json();
}
```

**Vercel Environment:**
- Deploy from Git: `github.com/yourusername/dijit.tech`
- Custom domain: `dijit.tech`
- Environment variables: None needed (all API calls server-side)

---

## 4. Security Implementation

### 4.1 Rate Limiting

**FastAPI Implementation:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Anonymous users: 10 requests/hour
@app.post("/api/analyze")
@limiter.limit("10/hour")
async def analyze_csv(request: Request, file: UploadFile):
    ...

# With API key: 100 requests/hour
@app.post("/api/analyze")
@limiter.limit("100/hour")
async def analyze_csv_premium(request: Request, file: UploadFile, api_key: str = Header(...)):
    if not verify_api_key(api_key):
        raise HTTPException(status_code=401)
    ...
```

### 4.2 Input Validation

```python
from pydantic import BaseModel, validator

class AnalyzeRequest(BaseModel):
    zip_code: str
    
    @validator('zip_code')
    def validate_zip(cls, v):
        if not v.isdigit() or len(v) != 5:
            raise ValueError('Invalid ZIP code')
        if v not in SUPPORTED_ZIPS:
            raise ValueError(f'ZIP {v} not yet supported')
        return v

# File validation
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@app.post("/api/analyze")
async def analyze_csv(file: UploadFile):
    # Check file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    # Check file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")
    
    # Validate CSV structure
    df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
    required_columns = ['Date', 'Usage', 'Reading Type']
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail="Invalid CSV format")
```

### 4.3 Data Privacy

```python
import tempfile
import time
from apscheduler.schedulers.background import BackgroundScheduler

# Temporary file storage
UPLOAD_DIR = "/app/uploads"
RETENTION_HOURS = 1

async def save_upload_temporarily(file: UploadFile) -> str:
    """Save file with auto-deletion after 1 hour"""
    timestamp = int(time.time())
    filename = f"{timestamp}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as f:
        f.write(await file.read())
    
    return filepath

def cleanup_old_uploads():
    """Delete files older than 1 hour"""
    now = time.time()
    for filename in os.listdir(UPLOAD_DIR):
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.isfile(filepath):
            file_age = now - os.path.getmtime(filepath)
            if file_age > RETENTION_HOURS * 3600:
                os.remove(filepath)

# Schedule cleanup
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_uploads, 'interval', minutes=15)
scheduler.start()
```

### 4.4 API Key Management (Optional Premium Feature)

```python
import secrets
from sqlalchemy import Table, Column, String, DateTime

# Database table
api_keys_table = Table(
    'api_keys',
    metadata,
    Column('key', String(64), primary_key=True),
    Column('email', String(255)),
    Column('created_at', DateTime),
    Column('requests_made', Integer, default=0),
    Column('rate_limit', Integer, default=100)  # Per hour
)

def generate_api_key(email: str) -> str:
    """Generate new API key"""
    key = secrets.token_urlsafe(32)
    # Store in database
    return key

def verify_api_key(key: str) -> bool:
    """Check if API key is valid"""
    # Query database
    return True  # or False
```

---

## 5. Implementation Steps

### Step 1: Create FastAPI Backend
```bash
# Create new file
touch src/powertochoose_mcp/api_server.py

# Install dependencies
pip install fastapi uvicorn slowapi python-multipart apscheduler
pip freeze > requirements.txt
```

### Step 2: Create Dockerfile.api
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

RUN mkdir -p /app/uploads

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "powertochoose_mcp.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 3: Deploy to Synology
```bash
# Transfer files via rsync
rsync -avz c:\code\powertochoose-mcp/ admin@your-nas:/volume1/docker/powertochoose-mcp/

# SSH and build
ssh admin@your-nas
cd /volume1/docker/powertochoose-mcp
sudo docker-compose build
sudo docker-compose up -d
```

### Step 4: Set Up Cloudflare Tunnel
```bash
# Follow Section 3.2 above
cloudflared tunnel create powertochoose
# Add DNS record in Cloudflare dashboard
# Start tunnel
```

### Step 5: Create Web Frontend
```bash
# On your dev machine
npx create-next-app@latest dijit-power-finder
cd dijit-power-finder

# Install dependencies
npm install @tanstack/react-query axios recharts

# Create components (see section 6 below)
```

### Step 6: Deploy Frontend to Vercel
```bash
# Push to GitHub
git init
git add .
git commit -m "Initial commit"
git push

# Connect to Vercel
# vercel.com → Import Project → Select repo
# Set custom domain: dijit.tech/power-plan-finder
```

---

## 6. Sample Web UI Code

### CSV Uploader Component

```typescript
// components/CSVUploader.tsx
import { useState } from 'react';
import { Upload } from 'lucide-react';

export default function CSVUploader({ onAnalyze }) {
  const [file, setFile] = useState<File | null>(null);
  const [zipCode, setZipCode] = useState('75074');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('csv_file', file);
      formData.append('zip_code', zipCode);

      const response = await fetch('https://api.dijit.tech/api/analyze', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      onAnalyze(data);
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="border-2 border-dashed rounded-lg p-8 text-center">
          <Upload className="mx-auto h-12 w-12 text-gray-400" />
          <label className="mt-4 block">
            <span className="sr-only">Choose CSV file</span>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-full file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100"
            />
          </label>
          <p className="mt-2 text-sm text-gray-500">
            Upload your ESIID meter data CSV (max 10MB)
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            ZIP Code
          </label>
          <input
            type="text"
            value={zipCode}
            onChange={(e) => setZipCode(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
            placeholder="75074"
          />
        </div>

        <button
          type="submit"
          disabled={!file || loading}
          className="w-full bg-blue-600 text-white py-3 rounded-lg
            disabled:bg-gray-300 disabled:cursor-not-allowed
            hover:bg-blue-700 transition"
        >
          {loading ? 'Analyzing...' : 'Find Best Plans'}
        </button>
      </form>
    </div>
  );
}
```

### Plan Recommendations Component

```typescript
// components/PlanRecommendations.tsx
export default function PlanRecommendations({ recommendations, usageAnalysis }) {
  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="mb-8 bg-blue-50 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-2">Your Usage Pattern</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-gray-600">Avg Monthly Usage</p>
            <p className="text-2xl font-bold">{usageAnalysis.avg_monthly_kwh} kWh</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Peak Time</p>
            <p className="text-2xl font-bold">{usageAnalysis.peak_time}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Pattern Type</p>
            <p className="text-2xl font-bold capitalize">{usageAnalysis.pattern_type}</p>
          </div>
        </div>
      </div>

      <h2 className="text-2xl font-bold mb-6">Recommended Plans</h2>
      
      <div className="space-y-4">
        {recommendations.map((plan, idx) => (
          <div key={idx} className="border rounded-lg p-6 hover:shadow-lg transition">
            <div className="flex justify-between items-start">
              <div>
                <h3 className="text-xl font-semibold">{plan.plan_name}</h3>
                <p className="text-gray-600">{plan.provider}</p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold text-blue-600">
                  ${plan.monthly_cost.toFixed(2)}
                </p>
                <p className="text-sm text-gray-600">per month</p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-gray-600">Renewable</p>
                <p className="font-semibold">{plan.renewable_percentage}%</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Contract</p>
                <p className="font-semibold">{plan.contract_months} months</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Cancellation Fee</p>
                <p className="font-semibold">
                  {plan.cancellation_fee ? `$${plan.cancellation_fee}` : 'None'}
                </p>
              </div>
            </div>

            <details className="mt-4">
              <summary className="cursor-pointer text-blue-600 hover:underline">
                View cost breakdown
              </summary>
              <div className="mt-2 bg-gray-50 rounded p-4 text-sm">
                <div className="flex justify-between py-1">
                  <span>Base Charge</span>
                  <span>${plan.breakdown.base_charge_usd}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span>Energy Charge</span>
                  <span>${plan.breakdown.energy_charge_usd}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span>TDU Delivery</span>
                  <span>${plan.breakdown.tdu_delivery_usd}</span>
                </div>
                <div className="flex justify-between py-1 border-t font-semibold">
                  <span>Total</span>
                  <span>${plan.breakdown.total_monthly_usd}</span>
                </div>
              </div>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 7. Cost Estimation

### Infrastructure Costs

| Component | Service | Cost |
|-----------|---------|------|
| MCP Backend | Synology DS920+ (owned) | $0/month |
| API Tunnel | Cloudflare Tunnel (free tier) | $0/month |
| Web Frontend | Vercel (hobby tier) | $0/month |
| LLM API | Google Gemini 2.0 Flash | ~$5-20/month* |
| Domain | dijit.tech (owned) | $0/month |

**Total: $5-20/month** (only Gemini API usage)

*Gemini Flash pricing:
- Free tier: 1500 requests/day
- Paid: $0.075 per 1M input tokens, $0.30 per 1M output tokens
- Estimated: 100-500 requests/day = $5-20/month

### Scaling Considerations

**Free Tier Limits:**
- Vercel: 100GB bandwidth, 100K serverless function executions
- Cloudflare: Unlimited bandwidth (reasonable use)
- Gemini: 1500 requests/day free

**If Traffic Grows:**
- Vercel Pro: $20/month (1TB bandwidth)
- Cloudflare Zero Trust: Still free
- Gemini: Pay-as-you-go (scales automatically)

---

## 8. Monitoring & Analytics

### Health Monitoring

```python
# api_server.py
from datetime import datetime

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "mcp_server": check_mcp_connection(),
        "database": {
            "total_plans": get_plan_count(),
            "last_scrape": get_last_scrape_time(),
            "zips_covered": ["75035", "75024", "75074", ...]
        },
        "api": {
            "requests_today": get_request_count_today(),
            "avg_response_time_ms": get_avg_response_time()
        }
    }

def check_mcp_connection() -> bool:
    try:
        response = httpx.get("http://localhost:8080/sse", timeout=2.0)
        return response.status_code == 200
    except:
        return False
```

### Usage Analytics

```python
# Log API requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Log to database
    log_api_request(
        endpoint=request.url.path,
        method=request.method,
        ip=request.client.host,
        duration_ms=duration * 1000,
        status_code=response.status_code
    )
    
    return response
```

---

## 9. Future Enhancements

1. **User Accounts**
   - Save favorite plans
   - Email alerts for better deals
   - Historical cost tracking

2. **Advanced Features**
   - Compare multiple addresses
   - Solar panel integration recommendations
   - EV charging optimization

3. **Premium Tier**
   - Higher rate limits (1000 req/day)
   - API access for developers
   - Custom alerts and notifications
   - Priority support

4. **Mobile App**
   - React Native wrapper
   - Push notifications
   - Offline plan browsing

5. **Expansion**
   - More ZIP codes (all Texas)
   - Other states (when deregulated)
   - Integration with utility APIs

---

## Next Steps

1. ✅ **Review this architecture** - Does it match your vision for dijit.tech?
2. ⏳ **Create FastAPI backend** - Implement api_server.py
3. ⏳ **Deploy to Synology** - Set up Docker containers
4. ⏳ **Configure Cloudflare Tunnel** - Expose API to internet
5. ⏳ **Build React frontend** - Create user interface
6. ⏳ **Deploy to Vercel** - Publish to dijit.tech
7. ⏳ **Testing** - End-to-end validation
8. ⏳ **Launch** - Go live!

**Estimated Timeline:** 2-3 days of focused work

**Document Version:** 1.0  
**Last Updated:** December 28, 2025
