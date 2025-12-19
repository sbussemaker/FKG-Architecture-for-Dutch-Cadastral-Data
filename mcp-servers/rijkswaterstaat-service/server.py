#!/usr/bin/env python3
"""
Rijkswaterstaat Service MCP Server
Ministry of Infrastructure and Water Management - Infrastructure and water data
"""

import json
import sys

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# Define namespace
GEO = Namespace("http://example.org/geospatial#")

# Initialize in-memory RDF graph
graph = Graph()
graph.bind("geo", GEO)


# Add sample Rijkswaterstaat data (infrastructure and water management)
def init_data():
    # Infrastructure near locations
    infrastructure = [
        # (locationId, infraId, infraType, condition, managedBy, description)
        ("LOC001", "INF-AMS-001", "bridge", "good", "Rijkswaterstaat", "IJ-tunnel entrance"),
        ("LOC002", "INF-UTR-001", "lock", "fair", "Rijkswaterstaat", "Weerdsluis"),
        ("LOC003", "INF-RTD-001", "bridge", "good", "Gemeente Rotterdam", "Erasmusbrug"),
    ]

    # Water bodies near locations
    water_bodies = [
        # (locationId, waterId, waterType, waterLevel, managedBy, name)
        ("LOC001", "WAT-AMS-001", "canal", 0.4, "Waternet", "Damrak canal"),
        ("LOC002", "WAT-UTR-001", "canal", 0.3, "Hoogheemraadschap", "Oudegracht"),
        ("LOC003", "WAT-RTD-001", "river", -0.2, "Rijkswaterstaat", "Nieuwe Maas"),
    ]

    # Roads near locations
    roads = [
        # (locationId, roadId, roadType, roadNumber, maxSpeed, condition)
        ("LOC001", "ROAD-A10", "highway", "A10", 100, "good"),
        ("LOC002", "ROAD-A12", "highway", "A12", 120, "fair"),
        ("LOC003", "ROAD-A15", "highway", "A15", 100, "good"),
    ]

    for loc_id, infra_id, infra_type, condition, managed, description in infrastructure:
        infra_uri = URIRef(f"http://example.org/infrastructure/{infra_id}")

        graph.add((infra_uri, RDF.type, GEO.Infrastructure))
        graph.add((infra_uri, GEO.locationId, Literal(loc_id)))
        graph.add((infra_uri, GEO.infrastructureType, Literal(infra_type)))
        graph.add((infra_uri, GEO.condition, Literal(condition)))
        graph.add((infra_uri, GEO.managedBy, Literal(managed)))
        graph.add((infra_uri, RDFS.label, Literal(description)))

    for loc_id, water_id, water_type, level, managed, name in water_bodies:
        water_uri = URIRef(f"http://example.org/water/{water_id}")

        graph.add((water_uri, RDF.type, GEO.WaterBody))
        graph.add((water_uri, GEO.locationId, Literal(loc_id)))
        graph.add((water_uri, GEO.waterType, Literal(water_type)))
        graph.add((water_uri, GEO.waterLevel, Literal(level, datatype=XSD.decimal)))
        graph.add((water_uri, GEO.managedBy, Literal(managed)))
        graph.add((water_uri, RDFS.label, Literal(name)))

    for loc_id, road_id, road_type, road_num, max_speed, condition in roads:
        road_uri = URIRef(f"http://example.org/roads/{road_id}")

        graph.add((road_uri, RDF.type, GEO.Road))
        graph.add((road_uri, GEO.locationId, Literal(loc_id)))
        graph.add((road_uri, GEO.roadType, Literal(road_type)))
        graph.add((road_uri, GEO.roadNumber, Literal(road_num)))
        graph.add((road_uri, GEO.maxSpeed, Literal(max_speed, datatype=XSD.integer)))
        graph.add((road_uri, GEO.condition, Literal(condition)))


init_data()


def get_infrastructure(location_id):
    """Get infrastructure data by location ID"""
    results = []

    for infra_uri in graph.subjects(RDF.type, GEO.Infrastructure):
        loc = str(graph.value(infra_uri, GEO.locationId))
        if loc == location_id:
            infra_type = str(graph.value(infra_uri, GEO.infrastructureType))
            condition = str(graph.value(infra_uri, GEO.condition))
            managed = str(graph.value(infra_uri, GEO.managedBy))
            description = str(graph.value(infra_uri, RDFS.label))

            results.append(
                {
                    "@id": str(infra_uri),
                    "@type": "geo:Infrastructure",
                    "geo:infrastructureType": infra_type,
                    "geo:condition": condition,
                    "geo:managedBy": managed,
                    "rdfs:label": description,
                }
            )

    # Also get water bodies
    for water_uri in graph.subjects(RDF.type, GEO.WaterBody):
        loc = str(graph.value(water_uri, GEO.locationId))
        if loc == location_id:
            water_type = str(graph.value(water_uri, GEO.waterType))
            level = str(graph.value(water_uri, GEO.waterLevel))
            managed = str(graph.value(water_uri, GEO.managedBy))
            name = str(graph.value(water_uri, RDFS.label))

            results.append(
                {
                    "@id": str(water_uri),
                    "@type": "geo:WaterBody",
                    "geo:waterType": water_type,
                    "geo:waterLevel": level,
                    "geo:managedBy": managed,
                    "rdfs:label": name,
                }
            )

    # Also get roads
    for road_uri in graph.subjects(RDF.type, GEO.Road):
        loc = str(graph.value(road_uri, GEO.locationId))
        if loc == location_id:
            road_type = str(graph.value(road_uri, GEO.roadType))
            road_num = str(graph.value(road_uri, GEO.roadNumber))
            max_speed = str(graph.value(road_uri, GEO.maxSpeed))
            condition = str(graph.value(road_uri, GEO.condition))

            results.append(
                {
                    "@id": str(road_uri),
                    "@type": "geo:Road",
                    "geo:roadType": road_type,
                    "geo:roadNumber": road_num,
                    "geo:maxSpeed": max_speed,
                    "geo:condition": condition,
                }
            )

    if not results:
        return None

    return {
        "@context": {
            "geo": "http://example.org/geospatial#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "geo:locationId": location_id,
        "@graph": results,
    }


def list_roads():
    """List all roads"""
    roads = []
    for road_uri in graph.subjects(RDF.type, GEO.Road):
        loc_id = str(graph.value(road_uri, GEO.locationId))
        road_type = str(graph.value(road_uri, GEO.roadType))
        road_num = str(graph.value(road_uri, GEO.roadNumber))
        condition = str(graph.value(road_uri, GEO.condition))

        roads.append(
            {
                "@id": str(road_uri),
                "@type": "geo:Road",
                "geo:locationId": loc_id,
                "geo:roadNumber": road_num,
                "geo:roadType": road_type,
                "geo:condition": condition,
            }
        )

    return {"@context": {"geo": "http://example.org/geospatial#"}, "@graph": roads}


def get_water_level(location_id):
    """Get water level data by location ID"""
    for water_uri in graph.subjects(RDF.type, GEO.WaterBody):
        loc = str(graph.value(water_uri, GEO.locationId))
        if loc == location_id:
            water_type = str(graph.value(water_uri, GEO.waterType))
            level = str(graph.value(water_uri, GEO.waterLevel))
            managed = str(graph.value(water_uri, GEO.managedBy))
            name = str(graph.value(water_uri, RDFS.label))

            return {
                "@context": {
                    "geo": "http://example.org/geospatial#",
                    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                },
                "@id": str(water_uri),
                "@type": "geo:WaterBody",
                "geo:locationId": location_id,
                "geo:waterType": water_type,
                "geo:waterLevel": level,
                "geo:managedBy": managed,
                "rdfs:label": name,
            }

    return None


def handle_request(request):
    """Handle MCP JSON-RPC request"""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "rijkswaterstaat-service", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "get_infrastructure",
                        "description": (
                            "Get infrastructure data (roads, bridges, water) by location ID. "
                            "Returns Rijkswaterstaat data in JSON-LD format."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": "The location ID (e.g., LOC001)",
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                    {
                        "name": "list_roads",
                        "description": (
                            "List all roads managed by Rijkswaterstaat. "
                            "Returns RDF data in JSON-LD format."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "get_water_level",
                        "description": (
                            "Get current water level data by location ID. Returns JSON-LD format."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": "The location ID (e.g., LOC001)",
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                ]
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "get_infrastructure":
            location_id = tool_args.get("location_id")
            result = get_infrastructure(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Infrastructure for location {location_id} not found",
                            }
                        ],
                        "isError": True,
                    },
                }

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }

        elif tool_name == "list_roads":
            result = list_roads()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }

        elif tool_name == "get_water_level":
            location_id = tool_args.get("location_id")
            result = get_water_level(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Water level data for location {location_id} not found",
                            }
                        ],
                        "isError": True,
                    },
                }

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    """Main MCP server loop using stdio transport"""
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
