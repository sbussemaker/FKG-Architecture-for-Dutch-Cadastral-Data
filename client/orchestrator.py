#!/usr/bin/env python3
"""
EAI Orchestration Backend
Manages Docker containers and acts as MCP client
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, TypedDict

import docker
import uvicorn
from docker.errors import ImageNotFound, NotFound
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from mcp_client import call_mcp_tool, list_mcp_tools
from pydantic import BaseModel, Field


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

# Reduce uvicorn logging noise
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# Docker client
docker_client = docker.from_env()


class ServiceConfig(TypedDict, total=False):
    name: str
    display_name: str
    description: str
    image: str
    build_path: str
    dockerfile: str
    container_name: str
    status: str
    rdf_entities: list[str]
    position: dict[str, int]
    is_agent: bool


# Service definitions
SERVICES: dict[str, ServiceConfig] = {
    "bag-service": {
        "name": "bag-service",
        "display_name": "BAG",
        "description": "Addresses & Buildings (Basisregistratie Adressen en Gebouwen)",
        "image": "eai-bag-service",
        "build_path": "../mcp-servers/bag-service",
        "dockerfile": "../Dockerfile.shared",
        "container_name": "eai-bag-service",
        "status": "stopped",
        "rdf_entities": ["Address", "Building"],
        "position": {"x": 50, "y": 50},
    },
    "bgt-service": {
        "name": "bgt-service",
        "display_name": "BGT",
        "description": "Large-Scale Topography (Basisregistratie Grootschalige Topografie)",
        "image": "eai-bgt-service",
        "build_path": "../mcp-servers/bgt-service",
        "dockerfile": "../Dockerfile.shared",
        "container_name": "eai-bgt-service",
        "status": "stopped",
        "rdf_entities": ["TopographicArea", "Road", "WaterBody"],
        "position": {"x": 50, "y": 550},
    },
    "brt-service": {
        "name": "brt-service",
        "display_name": "BRT",
        "description": "Topographic Maps (Basisregistratie Topografie)",
        "image": "eai-brt-service",
        "build_path": "../mcp-servers/brt-service",
        "dockerfile": "../Dockerfile.shared",
        "container_name": "eai-brt-service",
        "status": "stopped",
        "rdf_entities": ["GeographicName", "AdministrativeBoundary", "LandscapeFeature"],
        "position": {"x": 50, "y": 300},
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
        "position": {"x": 550, "y": 50},
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
        "position": {"x": 550, "y": 300},
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
        "is_agent": True,
    },
}


# Pydantic models
class Tool(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = Field(default=None, alias="inputSchema")


class Service(BaseModel):
    name: str
    display_name: str
    rdf_entities: list[str]
    tools: list[Tool]


class ServiceFull(BaseModel):
    name: str
    display_name: str
    description: str
    image: str
    container_name: str
    status: str
    rdf_entities: list[str]
    position: dict[str, int]
    is_agent: bool | None = None


class ServiceActionResponse(BaseModel):
    status: str
    container_id: str | None = None
    error: str | None = None


class QueryItem(BaseModel):
    service: str
    tool: str
    arguments: dict[str, Any] | None = None


class QueryRequest(BaseModel):
    queries: list[QueryItem]


class QueryResult(BaseModel):
    service: str | None = None
    tool: str | None = None
    result: Any = None
    error: str | None = None


class QueryResponse(BaseModel):
    results: list[QueryResult]


class OntologyResponse(BaseModel):
    ontology: str | None = None
    error: str | None = None


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting EAI Orchestration Backend...")
    logger.info("Building Docker images...")

    # Always rebuild images on startup
    for service in SERVICES.values():
        logger.info(f"Building {service['image']}...")
        docker_client.images.build(
            path=service["build_path"],
            dockerfile=service["dockerfile"],
            tag=service["image"],
            rm=True,
            forcerm=True,
        )
        logger.info(f"Built {service['image']}")

    update_service_status()
    logger.info(f"Log level set to: {LOG_LEVEL}")
    logger.info("Swagger UI available at http://localhost:5000/docs")

    yield

    logger.info("Shutting down...")


app = FastAPI(
    title="EAI Orchestration API",
    description="API for managing Docker containers and MCP services",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/services", response_model=list[Service], tags=["services"])
def list_services():
    """Get running services with their available tools"""
    update_service_status()
    result = []
    for service in SERVICES.values():
        if service["status"] != "running":
            continue
        tools = list_mcp_tools(docker_client, service["container_name"])
        result.append(
            Service(
                name=service["name"],
                display_name=service["display_name"],
                rdf_entities=service["rdf_entities"],
                tools=[Tool(**t) for t in tools],
            )
        )
    return result


@app.get("/api/services/all", response_model=list[ServiceFull], tags=["services"])
def list_all_services():
    """Get all services with full details (for dashboard)"""
    update_service_status()
    return [
        ServiceFull(
            name=service["name"],
            display_name=service["display_name"],
            description=service["description"],
            image=service["image"],
            container_name=service["container_name"],
            status=service["status"],
            rdf_entities=service["rdf_entities"],
            position=service["position"],
            is_agent=service.get("is_agent"),
        )
        for service in SERVICES.values()
    ]


@app.post(
    "/api/services/{service_name}/start", response_model=ServiceActionResponse, tags=["services"]
)
def start_service(service_name: str):
    """Start a service container"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    service = SERVICES[service_name]

    try:
        # Check if container exists
        try:
            container = docker_client.containers.get(service["container_name"])
            if container.status == "running":
                return ServiceActionResponse(status="already running")
            container.start()
        except NotFound:
            # Build image if needed
            try:
                docker_client.images.get(service["image"])
            except ImageNotFound:
                logger.info(f"Building image {service['image']}...")
                docker_client.images.build(path=service["build_path"], tag=service["image"])

            # Create and start container
            container_env = ENV_VARS if service.get("is_agent") else None

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

        time.sleep(1)
        update_service_status()

        return ServiceActionResponse(status="started", container_id=container.id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post(
    "/api/services/{service_name}/stop", response_model=ServiceActionResponse, tags=["services"]
)
def stop_service(service_name: str):
    """Stop a service container"""
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    service = SERVICES[service_name]

    try:
        container = docker_client.containers.get(service["container_name"])
        container.stop()
        update_service_status()
        return ServiceActionResponse(status="stopped")
    except NotFound:
        return ServiceActionResponse(status="not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/query", response_model=QueryResponse, tags=["query"])
def query_services(request: QueryRequest):
    """Execute a query across multiple services using MCP"""
    results = []
    for query in request.queries:
        if query.service not in SERVICES:
            results.append(QueryResult(error=f"Service {query.service} not found"))
            continue

        service = SERVICES[query.service]
        logger.info(f"Make call to {service}")
        result = call_mcp_tool(
            docker_client, service["container_name"], query.tool, query.arguments or {}
        )
        results.append(QueryResult(service=query.service, tool=query.tool, result=result))

    return QueryResponse(results=results)


@app.get("/api/ontology", response_model=OntologyResponse, tags=["ontology"])
def get_ontology():
    """Get the RDF ontology"""
    try:
        with open("../ontology/geospatial.ttl") as f:
            ontology = f.read()
        return Response(content=ontology, media_type="text/turtle")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level=LOG_LEVEL.lower())
