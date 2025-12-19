#!/usr/bin/env python3
"""
CBS Service MCP Server
Statistics Netherlands - Demographic and statistical data
"""

import json
import sys

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

# Define namespace
GEO = Namespace("http://example.org/geospatial#")

# Initialize in-memory RDF graph
graph = Graph()
graph.bind("geo", GEO)


# Add sample CBS data (statistical and demographic information)
def init_data():
    statistics = [
        # (locationId, municipality, population, households, avgIncome,
        #  popDensity, unemploymentRate)
        ("LOC001", "Amsterdam", 872680, 465242, 38500.0, 5135.0, 5.2),
        ("LOC002", "Utrecht", 361966, 183149, 35200.0, 3426.0, 4.8),
        ("LOC003", "Rotterdam", 651446, 342847, 31900.0, 3239.0, 6.5),
    ]

    for loc_id, municipality, pop, households, income, density, unemployment in statistics:
        location_uri = URIRef(f"http://example.org/locations/{loc_id}")
        stats_uri = URIRef(f"http://example.org/statistics/{loc_id}")

        # Location data
        graph.add((location_uri, RDF.type, GEO.Location))
        graph.add((location_uri, GEO.locationId, Literal(loc_id)))
        graph.add((location_uri, GEO.municipality, Literal(municipality)))

        # Statistical data
        graph.add((stats_uri, RDF.type, GEO.Municipality))
        graph.add((stats_uri, GEO.locationId, Literal(loc_id)))
        graph.add((stats_uri, GEO.municipality, Literal(municipality)))
        graph.add((stats_uri, GEO.population, Literal(pop, datatype=XSD.integer)))
        graph.add((stats_uri, GEO.households, Literal(households, datatype=XSD.integer)))
        graph.add((stats_uri, GEO.averageIncome, Literal(income, datatype=XSD.decimal)))
        graph.add((stats_uri, GEO.populationDensity, Literal(density, datatype=XSD.decimal)))
        graph.add((stats_uri, GEO.unemploymentRate, Literal(unemployment, datatype=XSD.decimal)))


init_data()


def get_statistics(location_id):
    """Get statistical data by location ID"""
    stats_uri = URIRef(f"http://example.org/statistics/{location_id}")

    # Check if statistics exist
    if (stats_uri, RDF.type, GEO.Municipality) not in graph:
        return None

    # Extract data
    municipality = str(graph.value(stats_uri, GEO.municipality))
    population = str(graph.value(stats_uri, GEO.population))
    households = str(graph.value(stats_uri, GEO.households))
    income = str(graph.value(stats_uri, GEO.averageIncome))
    density = str(graph.value(stats_uri, GEO.populationDensity))
    unemployment = str(graph.value(stats_uri, GEO.unemploymentRate))

    return {
        "@context": {"geo": "http://example.org/geospatial#"},
        "@id": str(stats_uri),
        "@type": "geo:Municipality",
        "geo:locationId": location_id,
        "geo:municipality": municipality,
        "geo:population": population,
        "geo:households": households,
        "geo:averageIncome": income,
        "geo:populationDensity": density,
        "geo:unemploymentRate": unemployment,
    }


def list_locations():
    """List all locations with basic statistics"""
    locations = []
    for stats_uri in graph.subjects(RDF.type, GEO.Municipality):
        loc_id = str(graph.value(stats_uri, GEO.locationId))
        municipality = str(graph.value(stats_uri, GEO.municipality))
        population = str(graph.value(stats_uri, GEO.population))

        locations.append(
            {
                "@id": str(stats_uri),
                "@type": "geo:Municipality",
                "geo:locationId": loc_id,
                "geo:municipality": municipality,
                "geo:population": population,
            }
        )

    return {"@context": {"geo": "http://example.org/geospatial#"}, "@graph": locations}


def get_demographics(location_id):
    """Get detailed demographic data by location ID"""
    stats_uri = URIRef(f"http://example.org/statistics/{location_id}")

    if (stats_uri, RDF.type, GEO.Municipality) not in graph:
        return None

    municipality = str(graph.value(stats_uri, GEO.municipality))
    population = int(str(graph.value(stats_uri, GEO.population)))
    households = int(str(graph.value(stats_uri, GEO.households)))

    # Calculate derived statistics
    avg_household_size = round(population / households, 2) if households > 0 else 0

    return {
        "@context": {"geo": "http://example.org/geospatial#"},
        "@id": str(stats_uri),
        "@type": "geo:Municipality",
        "geo:locationId": location_id,
        "geo:municipality": municipality,
        "geo:population": str(population),
        "geo:households": str(households),
        "derived:averageHouseholdSize": str(avg_household_size),
    }


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
                "serverInfo": {"name": "cbs-service", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "get_statistics",
                        "description": (
                            "Get statistical data by location ID. "
                            "Returns CBS demographic data in JSON-LD format."
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
                        "name": "list_locations",
                        "description": (
                            "List all locations with population data. "
                            "Returns RDF data in JSON-LD format."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "get_demographics",
                        "description": (
                            "Get detailed demographic breakdown by location ID. "
                            "Returns JSON-LD format."
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

        if tool_name == "get_statistics":
            location_id = tool_args.get("location_id")
            result = get_statistics(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Statistics for location {location_id} not found",
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

        elif tool_name == "list_locations":
            result = list_locations()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }

        elif tool_name == "get_demographics":
            location_id = tool_args.get("location_id")
            result = get_demographics(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Demographics for location {location_id} not found",
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
