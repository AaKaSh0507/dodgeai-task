FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Ensure data directory exists
RUN mkdir -p /app/data

EXPOSE 8000

# health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=40s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["sh", "-c", "python ingest.py && python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
