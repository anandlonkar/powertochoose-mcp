FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project configuration and source code
COPY pyproject.toml .
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir -e .

# Create directories for data
RUN mkdir -p /app/data/efls /app/data/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/powertochoose.db
ENV EFL_DIR=/app/data/efls
ENV LOG_DIR=/app/data/logs

# Default command (keeps container alive)
CMD ["tail", "-f", "/dev/null"]
