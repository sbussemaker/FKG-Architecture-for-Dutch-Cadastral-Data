FROM python:3.14-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir openai rdflib

# Copy server script
COPY server.py .

# Make script executable
RUN chmod +x server.py

# Run the MCP server
CMD ["python", "-u", "server.py"]
