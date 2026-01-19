#!/bin/bash
# Helper script to connect MCP Inspector to MCP servers
# Usage: ./scripts/inspect-mcp.sh <service-name> [--docker]

set -e

SERVICE=${1:-kadaster-service}
MODE=${2:-local}

VALID_SERVICES=("kadaster-service" "cbs-service" "rijkswaterstaat-service" "agent-service")

if [[ ! " ${VALID_SERVICES[@]} " =~ " ${SERVICE} " ]]; then
    echo "Error: Invalid service '${SERVICE}'"
    echo "Valid services: ${VALID_SERVICES[*]}"
    exit 1
fi

# Check if npx is available
if ! command -v npx &> /dev/null; then
    echo "Error: npx is required. Install Node.js first."
    exit 1
fi

if [[ "$MODE" == "--docker" ]]; then
    # Docker mode: connect to running container
    CONTAINER="eai-${SERVICE}"

    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
        echo "Error: Container '${CONTAINER}' is not running."
        echo "Start it first: curl -X POST http://localhost:5000/api/services/${SERVICE}/start"
        exit 1
    fi

    echo "Connecting MCP Inspector to ${SERVICE} via Docker..."
    npx @modelcontextprotocol/inspector \
        docker exec -i "${CONTAINER}" python -u server.py
else
    # Local mode: run server directly
    SERVER_DIR="$(dirname "$0")/../mcp-servers/${SERVICE}"

    if [[ ! -d "$SERVER_DIR" ]]; then
        echo "Error: Server directory not found: ${SERVER_DIR}"
        exit 1
    fi

    echo "Connecting MCP Inspector to ${SERVICE} locally..."

    if [[ "$SERVICE" == "agent-service" ]]; then
        # Agent service needs environment variables
        if [[ -f "$(dirname "$0")/../.env" ]]; then
            echo "Loading environment from .env file..."
            set -a
            source "$(dirname "$0")/../.env"
            set +a
        else
            echo "Warning: No .env file found. Agent service may not work without Azure OpenAI credentials."
        fi
    fi

    npx @modelcontextprotocol/inspector \
        uv run --directory "${SERVER_DIR}" \
        python server.py
fi
