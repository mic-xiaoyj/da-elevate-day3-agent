FROM python:3.11-slim

# Set environment settings
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY tools.yaml .
COPY .env.example .

# Expose server port
EXPOSE 8080

# Run ADK agent service
CMD ["python", "-m", "google.adk.cli", "web", "app", "--port", "8080", "--host", "0.0.0.0"]
