# PowerToChoose MCP Server - Synology NAS Deployment Guide

**Version:** 1.0  
**Target Platform:** Synology DSM 7.x with Docker  
**Date:** December 28, 2025

---

## Prerequisites

### On Your Synology NAS:
1. **Docker Package Installed**
   - Open Package Center → Search "Docker" → Install
   - Verify: SSH into NAS and run `docker --version`

2. **SSH Access Enabled**
   - Control Panel → Terminal & SNMP → Enable SSH service
   - Note your NAS IP address (e.g., `192.168.1.100`)

3. **Shared Folder Created**
   - File Station → Create shared folder: `docker`
   - Create subfolder: `docker/powertochoose-mcp`

### On Your Desktop:
4. **SSH Client** (PowerShell/Terminal)
5. **File Transfer Tool** (WinSCP, FileZilla, or rsync)

---

## Step 1: Transfer Files to Synology

### Option A: Using WinSCP (Windows)
1. Download WinSCP: https://winscp.net/
2. Connect to your NAS:
   - Protocol: SFTP
   - Host: Your NAS IP (e.g., `192.168.1.100`)
   - Port: 22
   - Username: Your admin account
   - Password: Your admin password

3. Navigate to `/volume1/docker/powertochoose-mcp`

4. Upload these files from `c:\code\powertochoose-mcp`:
   ```
   Dockerfile
   docker-compose.yml
   requirements.txt
   pyproject.toml
   src/ (entire folder)
   ```

### Option B: Using rsync (PowerShell/WSL)
```powershell
# From Windows PowerShell (with WSL or Git Bash)
rsync -avz --progress `
  --exclude '.venv' `
  --exclude '__pycache__' `
  --exclude '*.pyc' `
  --exclude 'data/' `
  c:\code\powertochoose-mcp/ `
  admin@192.168.1.100:/volume1/docker/powertochoose-mcp/
```

### Option C: Using SCP
```powershell
# Create archive locally
cd c:\code\powertochoose-mcp
tar -czf powertochoose-mcp.tar.gz `
  Dockerfile docker-compose.yml requirements.txt pyproject.toml src/

# Copy to NAS
scp powertochoose-mcp.tar.gz admin@192.168.1.100:/volume1/docker/

# SSH to NAS and extract
ssh admin@192.168.1.100
cd /volume1/docker
tar -xzf powertochoose-mcp.tar.gz -C powertochoose-mcp/
rm powertochoose-mcp.tar.gz
```

---

## Step 2: Update docker-compose.yml for Synology

SSH into your NAS:
```bash
ssh admin@192.168.1.100
cd /volume1/docker/powertochoose-mcp
```

Edit `docker-compose.yml`:
```bash
sudo vi docker-compose.yml
```

Update to this configuration:
```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    container_name: powertochoose-mcp
    command: python -m powertochoose_mcp.server --http 8080
    ports:
      - "8080:8080"
    volumes:
      - /volume1/docker/powertochoose-mcp/data:/app/data
      - /volume1/docker/powertochoose-mcp/src:/app/src
    environment:
      - DATABASE_PATH=/app/data/powertochoose.db
      - EFL_DIR=/app/data/efls
      - LOG_DIR=/app/data/logs
    restart: always
    networks:
      - mcp-network

networks:
  mcp-network:
    driver: bridge
```

**Key Changes:**
- Changed `command` from `tail -f /dev/null` to running the HTTP server
- Exposed port `8080`
- Changed volume paths to absolute Synology paths
- Added `restart: always` for auto-start after reboot
- Added network for future expansion

---

## Step 3: Create Data Directories

```bash
# Create data directories
mkdir -p /volume1/docker/powertochoose-mcp/data/efls
mkdir -p /volume1/docker/powertochoose-mcp/data/logs

# Set permissions
chmod -R 755 /volume1/docker/powertochoose-mcp/data
```

---

## Step 4: Build and Start the Container

### Build the Docker Image
```bash
cd /volume1/docker/powertochoose-mcp
sudo docker-compose build
```

Expected output:
```
Building mcp-server
Step 1/12 : FROM python:3.12-slim
...
Successfully built abc123def456
Successfully tagged powertochoose-mcp_mcp-server:latest
```

### Start the Container
```bash
sudo docker-compose up -d
```

Expected output:
```
Creating powertochoose-mcp ... done
```

### Verify Container is Running
```bash
sudo docker ps
```

Expected output:
```
CONTAINER ID   IMAGE                          COMMAND                  STATUS         PORTS
abc123def456   powertochoose-mcp_mcp-server   "python -m powertoc…"    Up 5 seconds   0.0.0.0:8080->8080/tcp
```

---

## Step 5: Test the MCP Server

### Test from NAS
```bash
curl http://localhost:8080/sse
```

Expected: SSE connection opens (keeps running, Ctrl+C to stop)

### Test from Your Desktop
Open browser or PowerShell:
```powershell
curl http://192.168.1.100:8080/sse
```

Or test with Python:
```python
import httpx

response = httpx.get("http://192.168.1.100:8080/sse")
print(response.status_code)  # Should be 200
```

---

## Step 6: Initial Data Scraping

Run the scraper to populate the database:

```bash
# SSH to NAS
ssh admin@192.168.1.100

# Run scraper for all ZIP codes
sudo docker exec powertochoose-mcp python -m powertochoose_mcp.scraper --all
```

This will take ~45-60 minutes to scrape all 7 ZIP codes. Monitor progress:
```bash
# Watch logs in real-time
sudo docker logs -f powertochoose-mcp
```

Or run scraper for today's bucket only (faster):
```bash
sudo docker exec powertochoose-mcp python -m powertochoose_mcp.scraper --today
```

---

## Step 7: Set Up Scheduled Scraping

### Option A: Synology Task Scheduler (Recommended)

1. **Open Task Scheduler**
   - Control Panel → Task Scheduler

2. **Create → Scheduled Task → User-defined script**

3. **General Tab:**
   - Task: `PowerToChoose Daily Scraper`
   - User: `root`
   - Enabled: ✅

4. **Schedule Tab:**
   - Run on the following days: Daily
   - First run time: `00:00`
   - Frequency: Once a day

5. **Task Settings Tab:**
   - User-defined script:
   ```bash
   docker exec powertochoose-mcp python -m powertochoose_mcp.scraper --today
   ```
   - Send run details by email: ✅ (optional)
   - Send run details only when script terminates abnormally: ✅

6. **Click OK** and test run:
   - Right-click task → Run
   - Check logs in `/volume1/docker/powertochoose-mcp/data/logs/`

### Option B: Cron Job (Advanced)

```bash
# SSH to NAS
ssh admin@192.168.1.100

# Edit crontab
sudo crontab -e

# Add this line (runs daily at midnight)
0 0 * * * /usr/local/bin/docker exec powertochoose-mcp python -m powertochoose_mcp.scraper --today >> /volume1/docker/powertochoose-mcp/scraper.log 2>&1
```

---

## Step 8: Update Your Notebook Connection

### For Local Network Access (Desktop on Same Network)

Update your notebook's Search Agent cell:
```python
powertochoose_toolset = McpToolset(
    connection_params=SseConnectionParams(
        url="http://192.168.1.100:8080/sse"  # Replace with your NAS IP
    )
)
```

### For Remote Access via Tailscale (Recommended)

1. **Install Tailscale on Synology**
   - Package Center → Search "Tailscale" → Install
   - Configure and authenticate

2. **Install Tailscale on Desktop**
   - Download from https://tailscale.com/download
   - Authenticate with same account

3. **Get Tailscale IP**
   ```bash
   # On NAS
   tailscale ip -4
   ```
   Example output: `100.64.1.10`

4. **Update Notebook**
   ```python
   powertochoose_toolset = McpToolset(
       connection_params=SseConnectionParams(
           url="http://100.64.1.10:8080/sse"  # Tailscale IP
       )
   )
   ```

**Benefits:**
- Works from anywhere (home, office, travel)
- Encrypted connection
- No port forwarding needed
- No public IP exposure

---

## Server Management Commands

### View Logs
```bash
# Real-time logs
sudo docker logs -f powertochoose-mcp

# Last 100 lines
sudo docker logs --tail 100 powertochoose-mcp

# Application logs
cat /volume1/docker/powertochoose-mcp/data/logs/requests_$(date +%Y-%m-%d).jsonl
```

### Restart Server
```bash
sudo docker restart powertochoose-mcp
```

### Stop Server
```bash
sudo docker-compose down
```

### Start Server
```bash
cd /volume1/docker/powertochoose-mcp
sudo docker-compose up -d
```

### Update Code
```bash
# Stop server
sudo docker-compose down

# Pull latest code (if using Git)
git pull

# Or copy new files via WinSCP/rsync

# Rebuild and restart
sudo docker-compose build
sudo docker-compose up -d
```

### Check Database
```bash
sudo docker exec -it powertochoose-mcp bash
sqlite3 /app/data/powertochoose.db "SELECT COUNT(*) FROM plans;"
sqlite3 /app/data/powertochoose.db "SELECT zip_code, COUNT(*) FROM plans GROUP BY zip_code;"
exit
```

---

## Monitoring & Maintenance

### Check Server Health
```bash
# Container status
sudo docker ps | grep powertochoose

# Resource usage
sudo docker stats powertochoose-mcp --no-stream

# Port listening
sudo netstat -tulpn | grep 8080
```

### Monitor Disk Space
```bash
# Data folder size
du -sh /volume1/docker/powertochoose-mcp/data

# Database size
ls -lh /volume1/docker/powertochoose-mcp/data/powertochoose.db

# EFL PDFs (should be ~500MB with 2-day retention)
du -sh /volume1/docker/powertochoose-mcp/data/efls
```

### Backup Strategy

**Automated Backup (Recommended):**
1. Control Panel → Shared Folder → `docker` → Properties
2. Enable snapshot replication (if supported)
3. Schedule: Daily at 02:00

**Manual Backup:**
```bash
# Backup entire project
sudo tar -czf /volume1/backups/powertochoose-$(date +%Y%m%d).tar.gz \
  /volume1/docker/powertochoose-mcp

# Backup database only
sudo cp /volume1/docker/powertochoose-mcp/data/powertochoose.db \
  /volume1/backups/powertochoose-db-$(date +%Y%m%d).db
```

---

## Troubleshooting

### Container Won't Start
```bash
# Check logs
sudo docker logs powertochoose-mcp

# Common issues:
# 1. Port 8080 already in use
sudo netstat -tulpn | grep 8080
# Kill conflicting process or change port in docker-compose.yml

# 2. Permission issues
sudo chmod -R 755 /volume1/docker/powertochoose-mcp
sudo chown -R admin:users /volume1/docker/powertochoose-mcp
```

### Can't Connect from Desktop
```bash
# Test from NAS first
curl http://localhost:8080/sse

# Check firewall
# Control Panel → Security → Firewall → Edit Rules → Create
# - Ports: Custom (8080)
# - Protocol: TCP
# - Source IP: All/Your desktop IP
# - Action: Allow

# Check Docker network
sudo docker network inspect powertochoose-mcp_mcp-network
```

### Scraper Not Running
```bash
# Check scheduled task history
# Control Panel → Task Scheduler → Select task → Action → View Result

# Test manual run
sudo docker exec powertochoose-mcp python -m powertochoose_mcp.scraper --today

# Check task logs
cat /volume1/docker/powertochoose-mcp/scraper.log
```

### Database Locked Errors
```bash
# Check WAL mode
sudo docker exec powertochoose-mcp bash -c \
  "sqlite3 /app/data/powertochoose.db 'PRAGMA journal_mode;'"

# Should return: wal

# If not, enable WAL:
sudo docker exec powertochoose-mcp bash -c \
  "sqlite3 /app/data/powertochoose.db 'PRAGMA journal_mode=WAL;'"
```

### High CPU Usage During Scraping
```bash
# Normal behavior (PDF parsing is CPU-intensive)
# Monitor:
sudo docker stats powertochoose-mcp

# If needed, limit CPU:
# Edit docker-compose.yml and add:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
```

---

## Firewall Configuration

### Allow Port 8080 (Local Network Only)

1. **Control Panel → Security → Firewall**
2. **Select Profile** (e.g., LAN)
3. **Edit Rules → Create**
   - Ports: `Custom` → `8080`
   - Protocol: `TCP`
   - Source IP: `192.168.1.0/24` (your local subnet)
   - Action: `Allow`
4. **Apply**

### For Tailscale (No Firewall Rules Needed)
- Tailscale handles encryption and access control
- No ports need to be opened on your router/firewall

---

## Performance Optimization

### Enable SSD Cache (If Available)
1. Storage Manager → SSD Cache
2. Create read-write cache for the volume containing Docker
3. Size: 50-100GB recommended

### Optimize Docker Storage
```bash
# Set Docker to use SSD if available
# Control Panel → Shared Folder
# Create 'docker' folder on SSD volume
# Symlink:
sudo ln -s /volume2/docker /volume1/docker  # If SSD is volume2
```

### Database Optimization
```bash
# Run weekly (add to Task Scheduler)
sudo docker exec powertochoose-mcp bash -c \
  "sqlite3 /app/data/powertochoose.db 'VACUUM; ANALYZE;'"
```

---

## Security Best Practices

1. **Change Default Ports** (if exposing to internet)
   ```yaml
   ports:
     - "9876:8080"  # Map external 9876 to internal 8080
   ```

2. **Enable HTTPS** (for remote access)
   - Use Synology's built-in reverse proxy
   - Control Panel → Login Portal → Advanced → Reverse Proxy
   - Add rule: `mcp.yournas.com:443` → `localhost:8080`

3. **Restrict SSH Access**
   - Control Panel → Terminal & SNMP → Advanced
   - Change SSH port from 22 to custom (e.g., 2222)
   - Limit login attempts

4. **Regular Updates**
   ```bash
   # Update base image monthly
   sudo docker-compose pull
   sudo docker-compose build
   sudo docker-compose up -d
   ```

---

## Next Steps

1. ✅ **Deploy to Synology** (you're doing this now!)
2. ⏳ **Test remote access** from your desktop
3. ⏳ **Verify scheduled scraping** runs at midnight
4. ⏳ **Set up backup routine**
5. ⏳ **Monitor for 7 days** to ensure stability
6. ⏳ **Add more ZIP codes** if needed
7. ⏳ **Consider HTTPS setup** for remote access

---

## Quick Reference

### Essential Commands
```bash
# SSH to NAS
ssh admin@192.168.1.100

# Check status
sudo docker ps | grep powertochoose

# View logs
sudo docker logs -f powertochoose-mcp

# Restart
sudo docker restart powertochoose-mcp

# Run scraper
sudo docker exec powertochoose-mcp python -m powertochoose_mcp.scraper --today

# Check database
sudo docker exec -it powertochoose-mcp bash
sqlite3 /app/data/powertochoose.db "SELECT COUNT(*) FROM plans;"
```

### Access URLs
- **Local Network:** `http://192.168.1.100:8080/sse`
- **Tailscale:** `http://100.64.1.x:8080/sse`
- **Test Endpoint:** `curl http://localhost:8080/sse`

### File Locations
- **Project:** `/volume1/docker/powertochoose-mcp/`
- **Database:** `/volume1/docker/powertochoose-mcp/data/powertochoose.db`
- **EFL PDFs:** `/volume1/docker/powertochoose-mcp/data/efls/`
- **Logs:** `/volume1/docker/powertochoose-mcp/data/logs/`

---

## Support & Troubleshooting

**Common Issues:**
- Port conflicts → Change port in docker-compose.yml
- Permission errors → `sudo chmod -R 755 /volume1/docker/powertochoose-mcp`
- Can't connect → Check firewall rules
- Database locked → Verify WAL mode enabled

**Getting Help:**
- Check logs: `sudo docker logs powertochoose-mcp`
- Review this guide's troubleshooting section
- Test with `curl http://localhost:8080/sse` from NAS first

---

**Document Version:** 1.0  
**Last Updated:** December 28, 2025  
**Tested On:** Synology DSM 7.2, Docker 20.10.23
