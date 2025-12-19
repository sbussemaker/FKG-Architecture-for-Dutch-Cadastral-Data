#!/usr/bin/env python3
"""
EAI Orchestration Backend
Manages Docker containers and acts as MCP client
"""

import json
import logging
import os
import sys
import time

import docker
from docker.errors import ImageNotFound, NotFound
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def load_env_file(env_path):
    """Load environment variables from .env file"""
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


# Load .env file from project root
env_file_path = os.path.join(os.path.dirname(__file__), "..", ".env")
ENV_VARS = load_env_file(env_file_path)

# Configure logging based on LOG_LEVEL from .env
LOG_LEVEL = ENV_VARS.get("LOG_LEVEL", "DEBUG").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("/tmp/orchestrator.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Reduce Flask/werkzeug logging noise (only show warnings and errors)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

# Docker client
docker_client = docker.from_env()

# Service definitions
SERVICES = {
    "kadaster-service": {
        "name": "kadaster-service",
        "display_name": "Kadaster",
        "description": "Dutch Land Registry - Cadastral data",
        "image": "eai-kadaster-service",
        "build_path": "../mcp-servers/kadaster-service",
        "container_name": "eai-kadaster-service",
        "status": "stopped",
        "rdf_entities": ["Property", "Location"],
        "position": {"x": 50, "y": 50},
    },
    "cbs-service": {
        "name": "cbs-service",
        "display_name": "CBS",
        "description": "Statistics Netherlands - Demographics",
        "image": "eai-cbs-service",
        "build_path": "../mcp-servers/cbs-service",
        "container_name": "eai-cbs-service",
        "status": "stopped",
        "rdf_entities": ["Municipality", "Statistics"],
        "position": {"x": 300, "y": 50},
    },
    "rijkswaterstaat-service": {
        "name": "rijkswaterstaat-service",
        "display_name": "Rijkswaterstaat",
        "description": "Infrastructure & Water Management",
        "image": "eai-rijkswaterstaat-service",
        "build_path": "../mcp-servers/rijkswaterstaat-service",
        "container_name": "eai-rijkswaterstaat-service",
        "status": "stopped",
        "rdf_entities": ["Infrastructure", "WaterBody", "Road"],
        "position": {"x": 550, "y": 50},
    },
    "agent-service": {
        "name": "agent-service",
        "display_name": "AI Agent",
        "description": "Intelligent agent (queries all services)",
        "image": "eai-agent-service",
        "build_path": "../mcp-servers/agent-service",
        "container_name": "eai-agent-service",
        "status": "stopped",
        "rdf_entities": ["Agent"],
        "position": {"x": 300, "y": 300},
        "is_agent": True,  # Mark this as special
    },
}


def update_service_status():
    """Update service statuses based on running containers"""
    try:
        containers = docker_client.containers.list(all=True)
        for service in SERVICES.values():
            found = False
            for container in containers:
                if container.name == service["container_name"]:
                    service["status"] = container.status
                    found = True
                    break
            if not found:
                service["status"] = "stopped"
    except Exception as e:
        logger.error(f"Error updating status: {e}")


def read_docker_stream(socket, _stream_type_filter=None):
    """
    Read from Docker multiplexed stream

    Args:
        socket: Docker socket
        _stream_type_filter: If specified, only return data from this stream (1=stdout, 2=stderr)
                            (Currently unused but kept for API compatibility)

    Returns:
        Decoded string data from the specified stream type
    """
    result = b""
    stderr_logs = []

    while True:
        # Read Docker multiplexing header (8 bytes)
        header = socket._sock.recv(8)
        if len(header) < 8:
            break

        stream_type = header[0]
        # Size is in bytes 4-8 (big-endian uint32)
        size = int.from_bytes(header[4:8], byteorder="big")

        # Read the payload
        payload = b""
        while len(payload) < size:
            chunk = socket._sock.recv(size - len(payload))
            if not chunk:
                break
            payload += chunk

        if stream_type == 0x02:  # stderr
            # Log stderr messages
            try:
                stderr_msg = payload.decode("utf-8", errors="replace").strip()
                if stderr_msg:
                    stderr_logs.append(stderr_msg)
                    logger.info(f"[Agent stderr] {stderr_msg}")
            except Exception as e:
                logger.warning(f"Error decoding stderr: {e}")
        elif stream_type == 0x01:  # stdout
            result += payload
            # Check if we have a complete JSON-RPC message (ends with newline)
            if payload.endswith(b"\n"):
                break

    # Log any collected stderr at the end
    if stderr_logs:
        logger.debug(f"Collected {len(stderr_logs)} stderr messages from agent")

    return result.decode("utf-8", errors="replace").strip()


def call_mcp_tool(container_name, tool_name, arguments=None):
    """Call an MCP tool in a running container"""
    if arguments is None:
        arguments = {}
    try:
        container = docker_client.containers.get(container_name)
        if container.status != "running":
            return {"error": f"Container {container_name} is not running"}

        # Initialize MCP connection
        init_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "eai-orchestrator", "version": "1.0.0"},
                    },
                }
            )
            + "\n"
        )

        exec_result = container.exec_run(
            "python -u server.py",
            stdin=True,
            stdout=True,
            stderr=True,  # Capture stderr for logging
            detach=False,
            tty=False,
            socket=True,
        )

        socket = exec_result.output
        socket._sock.sendall(init_request.encode())

        # Read initialization response
        init_response = read_docker_stream(socket)
        logger.info(f"Init response: {init_response[:200]}")

        # Call the tool
        tool_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                }
            )
            + "\n"
        )

        socket._sock.sendall(tool_request.encode())

        # Read tool response
        decoded_response = read_docker_stream(socket)
        socket._sock.close()

        logger.info(f"Tool response (first 200 chars): {decoded_response[:200]}")

        try:
            result = json.loads(decoded_response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response text: {decoded_response}")
            return {"error": f"Invalid JSON response: {str(e)}"}

        return result

    except Exception as e:
        import traceback

        logger.error(f"Error in call_mcp_tool: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}


@app.route("/api/services", methods=["GET"])
def get_services():
    """Get all services and their statuses"""
    update_service_status()
    return jsonify(list(SERVICES.values()))


@app.route("/api/services/<service_name>/start", methods=["POST"])
def start_service(service_name):
    """Start a service container"""
    if service_name not in SERVICES:
        return jsonify({"error": "Service not found"}), 404

    service = SERVICES[service_name]

    try:
        # Check if container exists
        try:
            container = docker_client.containers.get(service["container_name"])
            if container.status == "running":
                return jsonify({"status": "already running"})
            container.start()
        except NotFound:
            # Build image if needed
            try:
                docker_client.images.get(service["image"])
            except ImageNotFound:
                logger.info(f"Building image {service['image']}...")
                docker_client.images.build(path=service["build_path"], tag=service["image"])

            # Create and start container
            # Pass environment variables to agent service
            container_env = ENV_VARS if service.get("is_agent") else None

            # Mount Docker socket for agent service (needs to exec into other containers)
            volumes = (
                {"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}}
                if service.get("is_agent")
                else None
            )

            container = docker_client.containers.run(
                service["image"],
                name=service["container_name"],
                detach=True,
                stdin_open=True,
                tty=False,
                environment=container_env,
                volumes=volumes,
            )

        # Wait a moment for container to start
        time.sleep(1)
        update_service_status()

        return jsonify({"status": "started", "container_id": container.id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/services/<service_name>/stop", methods=["POST"])
def stop_service(service_name):
    """Stop a service container"""
    if service_name not in SERVICES:
        return jsonify({"error": "Service not found"}), 404

    service = SERVICES[service_name]

    try:
        container = docker_client.containers.get(service["container_name"])
        container.stop()
        update_service_status()
        return jsonify({"status": "stopped"})
    except NotFound:
        return jsonify({"status": "not found"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/query", methods=["POST"])
def query_services():
    """Execute a query across multiple services using MCP"""
    data = request.json
    queries = data.get("queries", [])

    results = []
    for query in queries:
        service_name = query.get("service")
        tool_name = query.get("tool")
        arguments = query.get("arguments", {})

        if service_name not in SERVICES:
            results.append({"error": f"Service {service_name} not found"})
            continue

        service = SERVICES[service_name]
        logger.info(f"Make call to {service}")
        result = call_mcp_tool(service["container_name"], tool_name, arguments)
        results.append({"service": service_name, "tool": tool_name, "result": result})

    return jsonify({"results": results})


@app.route("/api/ontology", methods=["GET"])
def get_ontology():
    """Get the RDF ontology"""
    try:
        with open("../ontology/geospatial.ttl") as f:
            ontology = f.read()
        return jsonify({"ontology": ontology})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logger.info("Starting EAI Orchestration Backend...")
    logger.info("Building Docker images...")

    # Always rebuild images on startup (like --build flag)
    for service in SERVICES.values():
        logger.info(f"Building {service['image']}...")
        docker_client.images.build(
            path=service["build_path"],
            tag=service["image"],
            rm=True,  # Remove intermediate containers
            forcerm=True,  # Always remove intermediate containers
        )
        logger.info(f"✓ Built {service['image']}")

    update_service_status()
    logger.info("Starting Flask server on port 5000...")
    logger.info(f"Log level set to: {LOG_LEVEL}")

    # Set Flask debug mode based on log level
    debug_mode = LOG_LEVEL == "DEBUG"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
