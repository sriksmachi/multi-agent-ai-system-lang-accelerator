FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy core shared modules
COPY core ./core

# Copy writer agent code
COPY agents/__init__.py ./agents/__init__.py
COPY agents/writer_agent ./agents/writer_agent

# Install Python dependencies
COPY agents/writer_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "agents.writer_agent.main:app", "--host", "0.0.0.0", "--port", "8003"]
