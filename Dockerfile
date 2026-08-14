FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + Node.js (for ELK.js layout)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# Install ELK.js (npm dependency)
RUN cd /app/backend && npm install

# Create __init__.py if not exists
RUN touch /app/backend/__init__.py

EXPOSE 8000

ENV PORT=8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
