FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy core shared modules
COPY core ./core

# Copy researcher agent code
COPY agents/__init__.py ./agents/__init__.py
COPY agents/researcher_agent ./agents/researcher_agent

# Install Python dependencies
COPY agents/researcher_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8002/health || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "agents.researcher_agent.main:app", "--host", "0.0.0.0", "--port", "8002"]
