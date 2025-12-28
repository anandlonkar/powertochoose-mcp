"""Request logging utilities."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from ..config import LOG_DIR


def log_request_to_jsonl(tool_name: str, parameters: Dict[str, Any], result_count: int):
    """Log an MCP request to JSONL file.

    Args:
        tool_name: Name of the MCP tool
        parameters: Tool parameters
        result_count: Number of results returned
    """
    # Create log entry
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "tool_name": tool_name,
        "parameters": parameters,
        "result_count": result_count,
        "classifications_used": parameters.get("classifications"),
    }

    # Determine log file (one file per day)
    log_file = LOG_DIR / f"requests_{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"

    # Append to JSONL file
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def cleanup_old_log_files(retention_days: int):
    """Delete log files older than retention period.

    Args:
        retention_days: Number of days to retain logs
    """
    cutoff_date = datetime.utcnow().timestamp() - (retention_days * 86400)

    for log_file in LOG_DIR.glob("requests_*.jsonl"):
        if log_file.stat().st_mtime < cutoff_date:
            log_file.unlink()
