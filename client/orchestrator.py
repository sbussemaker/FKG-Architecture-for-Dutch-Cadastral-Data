#!/usr/bin/env python3
"""
EAI Orchestration Backend
Manages Docker containers and acts as MCP client
"""

import logging
import os
import sys
import time

import docker
from docker.errors import ImageNotFound, NotFound
from flask import Flask
from flask_cors import CORS
from flask_restx import Api, Resource, fields
from mcp_client import call_mcp_tool, list_mcp_tools

app = Flask(__name__)
CORS(app)

# Configure Swagger/OpenAPI
api = Api(
    app,
    version="1.0.0",
    title="EAI Orchestration API",
    description="API for managing Docker containers and MCP services",
    doc="/swagger",
)

# Define namespaces
ns_services = api.namespace("api/services", description="Service management operations")
ns_query = api.namespace("api", description="Query operations")
ns_ontology = api.namespace("api", description="Ontology operations")


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
        "dockerfile": "../Dockerfile.shared",
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
        "dockerfile": "../Dockerfile.shared",
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
        "dockerfile": "../Dockerfile.shared",
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
        "dockerfile": "Dockerfile",
        "container_name": "eai-agent-service",
        "status": "stopped",
        "rdf_entities": ["Agent"],
        "position": {"x": 300, "y": 300},
        "is_agent": True,  # Mark this as special
    },
}

# API Models for Swagger documentation
tool_model = api.model(
    "Tool",
    {
        "name": fields.String(description="Tool name"),
        "description": fields.String(description="Tool description"),
        "inputSchema": fields.Raw(description="JSON Schema for tool input"),
    },
)

service_model = api.model(
    "Service",
    {
        "name": fields.String(description="Service identifier"),
        "display_name": fields.String(description="Human-readable service name"),
        "rdf_entities": fields.List(fields.String, description="RDF entities handled by service"),
        "tools": fields.List(fields.Nested(tool_model), description="Available MCP tools"),
    },
)

service_full_model = api.model(
    "ServiceFull",
    {
        "name": fields.String(description="Service identifier"),
        "display_name": fields.String(description="Human-readable service name"),
        "description": fields.String(description="Service description"),
        "image": fields.String(description="Docker image name"),
        "container_name": fields.String(description="Docker container name"),
        "status": fields.String(description="Current service status"),
        "rdf_entities": fields.List(fields.String, description="RDF entities handled by service"),
        "position": fields.Raw(description="UI position coordinates"),
        "is_agent": fields.Boolean(description="Whether this is an agent service"),
    },
)

service_action_response = api.model(
    "ServiceActionResponse",
    {
        "status": fields.String(description="Action result status"),
        "container_id": fields.String(description="Container ID (for start action)"),
        "error": fields.String(description="Error message if action failed"),
    },
)

query_item = api.model(
    "QueryItem",
    {
        "service": fields.String(required=True, description="Service name to query"),
        "tool": fields.String(required=True, description="MCP tool name to call"),
        "arguments": fields.Raw(description="Arguments to pass to the tool"),
    },
)

query_request = api.model(
    "QueryRequest",
    {
        "queries": fields.List(
            fields.Nested(query_item), required=True, description="List of queries"
        ),
    },
)

query_result = api.model(
    "QueryResult",
    {
        "service": fields.String(description="Service that was queried"),
        "tool": fields.String(description="Tool that was called"),
        "result": fields.Raw(description="Tool execution result"),
    },
)

query_response = api.model(
    "QueryResponse",
    {
        "results": fields.List(fields.Nested(query_result), description="List of query results"),
    },
)

ontology_response = api.model(
    "OntologyResponse",
    {
        "ontology": fields.String(description="RDF ontology in Turtle format"),
        "error": fields.String(description="Error message if retrieval failed"),
    },
)


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


@ns_services.route("")
class ServiceList(Resource):
    @ns_services.doc("list_services")
    @ns_services.marshal_list_with(service_model)
    def get(self):
        """Get running services with their available tools"""
        update_service_status()
        result = []
        for service in SERVICES.values():
            if service["status"] != "running":
                continue
            tools = list_mcp_tools(docker_client, service["container_name"])
            result.append(
                {
                    "name": service["name"],
                    "display_name": service["display_name"],
                    "rdf_entities": service["rdf_entities"],
                    "tools": tools,
                }
            )
        return result


@ns_services.route("/all")
class ServiceListAll(Resource):
    @ns_services.doc("list_all_services")
    @ns_services.marshal_list_with(service_full_model)
    def get(self):
        """Get all services with full details (for dashboard)"""
        update_service_status()
        return list(SERVICES.values())


@ns_services.route("/<string:service_name>/start")
@ns_services.param("service_name", "The service identifier")
class ServiceStart(Resource):
    @ns_services.doc("start_service")
    @ns_services.marshal_with(service_action_response)
    @ns_services.response(404, "Service not found")
    @ns_services.response(500, "Internal server error")
    def post(self, service_name):
        """Start a service container"""
        if service_name not in SERVICES:
            api.abort(404, f"Service {service_name} not found")

        service = SERVICES[service_name]

        try:
            # Check if container exists
            try:
                container = docker_client.containers.get(service["container_name"])
                if container.status == "running":
                    return {"status": "already running"}
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

            return {"status": "started", "container_id": container.id}

        except Exception as e:
            api.abort(500, str(e))


@ns_services.route("/<string:service_name>/stop")
@ns_services.param("service_name", "The service identifier")
class ServiceStop(Resource):
    @ns_services.doc("stop_service")
    @ns_services.marshal_with(service_action_response)
    @ns_services.response(404, "Service not found")
    @ns_services.response(500, "Internal server error")
    def post(self, service_name):
        """Stop a service container"""
        if service_name not in SERVICES:
            api.abort(404, f"Service {service_name} not found")

        service = SERVICES[service_name]

        try:
            container = docker_client.containers.get(service["container_name"])
            container.stop()
            update_service_status()
            return {"status": "stopped"}
        except NotFound:
            return {"status": "not found"}
        except Exception as e:
            api.abort(500, str(e))


@ns_query.route("/query")
class Query(Resource):
    @ns_query.doc("query_services")
    @ns_query.expect(query_request)
    @ns_query.marshal_with(query_response)
    def post(self):
        """Execute a query across multiple services using MCP"""
        data = api.payload
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
            result = call_mcp_tool(docker_client, service["container_name"], tool_name, arguments)
            results.append({"service": service_name, "tool": tool_name, "result": result})

        return {"results": results}


@ns_ontology.route("/ontology")
class Ontology(Resource):
    @ns_ontology.doc("get_ontology")
    @ns_ontology.marshal_with(ontology_response)
    @ns_ontology.response(500, "Internal server error")
    def get(self):
        """Get the RDF ontology"""
        try:
            with open("../ontology/geospatial.ttl") as f:
                ontology = f.read()
            return {"ontology": ontology}
        except Exception as e:
            api.abort(500, str(e))


if __name__ == "__main__":
    logger.info("Starting EAI Orchestration Backend...")
    logger.info("Building Docker images...")

    # Always rebuild images on startup (like --build flag)
    for service in SERVICES.values():
        logger.info(f"Building {service['image']}...")
        docker_client.images.build(
            path=service["build_path"],
            dockerfile=service["dockerfile"],
            tag=service["image"],
            rm=True,  # Remove intermediate containers
            forcerm=True,  # Always remove intermediate containers
        )
        logger.info(f"Built {service['image']}")

    update_service_status()
    logger.info("Starting Flask server on port 5000...")
    logger.info(f"Log level set to: {LOG_LEVEL}")
    logger.info("Swagger UI available at http://localhost:5000/swagger")

    # Set Flask debug mode based on log level
    debug_mode = LOG_LEVEL == "DEBUG"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
