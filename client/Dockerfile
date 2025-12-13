FROM python:3.14-slim

WORKDIR /app

# Install Docker CLI
RUN apt-get update && \
    apt-get install -y docker.io && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY orchestrator.py .

# Expose port
EXPOSE 5000

# Run orchestrator
CMD ["python", "-u", "orchestrator.py"]
