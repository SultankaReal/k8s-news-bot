FROM python:3.12-slim

WORKDIR /app

# System deps for feedparser + requests
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/

# Data volume for SQLite state
VOLUME ["/data"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/data/state.db \
    LOG_LEVEL=INFO

CMD ["python", "-m", "src.main"]
