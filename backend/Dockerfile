FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Expose port
EXPOSE 8000

# Run with gunicorn: --preload shares the precomputed cache across forked workers
# --access-logfile - : log to stdout
# --error-logfile - : log errors to stderr
# --log-level info : set log level
CMD ["gunicorn", "main:app", "--preload", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info"]
