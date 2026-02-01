#!/usr/bin/env python3
"""
CBS Service MCP Server
======================

Data Source: Statistics Netherlands (CBS - Centraal Bureau voor de Statistiek - cbs.nl)

Purpose:
    Provides official Dutch statistical data including population counts, household
    statistics, income data, unemployment rates, and population density metrics
    for municipalities in the Netherlands.

Ontology (RDF Namespace: http://imx-geo-prime.org/geospatial#):
    - geo:Location: Geographic location reference
        - geo:locationId: Unique identifier (e.g., "LOC001")
        - geo:municipality: Municipality/city name

    - geo:Municipality: Statistical data for a municipality
        - geo:locationId: Links to corresponding Location
        - geo:municipality: Municipality name
        - geo:population: Total inhabitants (xsd:integer)
        - geo:households: Number of households (xsd:integer)
        - geo:averageIncome: Average annual income in EUR (xsd:decimal)
        - geo:populationDensity: Inhabitants per km² (xsd:decimal)
        - geo:unemploymentRate: Unemployment percentage (xsd:decimal)

Derived Statistics:
    - averageHouseholdSize: Calculated as population / households (not raw CBS data)

Tool Discovery Pattern:
    1. Use find_location(query) to search by municipality name
    2. Get locationId from results
    3. Use get_statistics(location_id) for comprehensive data, or
       get_demographics(location_id) for household-focused data

Cross-Service Linking:
    The geo:locationId is consistent across all MCP services (Kadaster, CBS,
    Rijkswaterstaat), allowing data from different sources to be combined
    for the same geographic location.

Response Format: JSON-LD with @context for semantic interoperability
"""

import json
import sys

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

# Define namespace
GEO = Namespace("http://imx-geo-prime.org/geospatial#")

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
        location_uri = URIRef(f"http://imx-geo-prime.org/locations/{loc_id}")
        stats_uri = URIRef(f"http://imx-geo-prime.org/statistics/{loc_id}")

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
    stats_uri = URIRef(f"http://imx-geo-prime.org/statistics/{location_id}")

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
        "@context": {"geo": "http://imx-geo-prime.org/geospatial#"},
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

    return {"@context": {"geo": "http://imx-geo-prime.org/geospatial#"}, "@graph": locations}


def find_location(query):
    """Find locations by searching municipality name or location ID"""
    query_lower = query.lower()
    results = []

    for stats_uri in graph.subjects(RDF.type, GEO.Municipality):
        loc_id = str(graph.value(stats_uri, GEO.locationId))
        municipality = str(graph.value(stats_uri, GEO.municipality))

        # Search in municipality name and location ID
        if query_lower in municipality.lower() or query_lower in loc_id.lower():
            population = str(graph.value(stats_uri, GEO.population))
            results.append(
                {
                    "@type": "geo:Municipality",
                    "geo:locationId": loc_id,
                    "geo:municipality": municipality,
                    "geo:population": population,
                }
            )

    return {"@context": {"geo": "http://imx-geo-prime.org/geospatial#"}, "@graph": results}


def get_demographics(location_id):
    """Get detailed demographic data by location ID"""
    stats_uri = URIRef(f"http://imx-geo-prime.org/statistics/{location_id}")

    if (stats_uri, RDF.type, GEO.Municipality) not in graph:
        return None

    municipality = str(graph.value(stats_uri, GEO.municipality))
    population = int(str(graph.value(stats_uri, GEO.population)))
    households = int(str(graph.value(stats_uri, GEO.households)))

    # Calculate derived statistics
    avg_household_size = round(population / households, 2) if households > 0 else 0

    return {
        "@context": {"geo": "http://imx-geo-prime.org/geospatial#"},
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
                "serverInfo": {
                    "name": "cbs-service",
                    "version": "1.0.0",
                    "description": (
                        "CBS (Centraal Bureau voor de Statistiek / Statistics Netherlands) "
                        "MCP Server. Provides official Dutch statistical data including "
                        "population counts, household statistics, income data, and economic "
                        "indicators. Data source: CBS StatLine (cbs.nl). "
                        "Use this service for questions about: population numbers, "
                        "demographics, household counts, average income, unemployment rates, "
                        "and population density."
                    ),
                },
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "find_location",
                        "description": (
                            "Search for municipalities by name to get their location identifiers. "
                            "USE THIS TOOL FIRST when you don't know the location ID. "
                            "This is the discovery tool for the CBS database. "
                            "WORKFLOW: Call find_location('Amsterdam') to get LOC001, then use "
                            "that ID with get_statistics or get_demographics. "
                            "RETURNS: JSON-LD array of matching municipalities with: locationId "
                            "(use this ID for other CBS tools), municipality name, population. "
                            "SEARCH EXAMPLES: 'Amsterdam' returns LOC001, 'Utrecht' returns "
                            "LOC002, 'Rotterdam' returns LOC003. Partial matches work."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": (
                                        "Search term: municipality/city name (e.g., 'Amsterdam') "
                                        "or partial name (e.g., 'dam'). Case-insensitive matching."
                                    ),
                                }
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_statistics",
                        "description": (
                            "Retrieve comprehensive statistical data for a municipality from "
                            "CBS (Statistics Netherlands). "
                            "PREREQUISITE: First use find_location to get valid location IDs, "
                            "or use list_locations to see all available municipalities. "
                            "USE THIS TOOL WHEN: You need population numbers, income statistics, "
                            "unemployment data, or population density for a specific location. "
                            "RETURNS: JSON-LD with fields: municipality (city name), "
                            "population (total inhabitants as integer), households (number of "
                            "households), averageIncome (in EUR per year), populationDensity "
                            "(inhabitants per km²), unemploymentRate (percentage). "
                            "DATA SEMANTICS: Population uses geo:population predicate, linked to "
                            "municipality via geo:locationId. All monetary values in EUR. "
                            "EXAMPLE: For LOC001 (Amsterdam), returns population 872,680, "
                            "465,242 households, avg income €38,500, density 5,135/km²."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": (
                                        "Location identifier obtained from find_location or "
                                        "list_locations. Format: 'LOC' followed by digits "
                                        "(e.g., 'LOC001' for Amsterdam)."
                                    ),
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                    {
                        "name": "list_locations",
                        "description": (
                            "List ALL municipalities in the CBS database with basic population "
                            "data. USE THIS TOOL WHEN: You need to discover available locations, "
                            "compare populations across cities, or get a quick overview. "
                            "ALTERNATIVE TO: find_location (use when you don't have a search "
                            "term). RETURNS: JSON-LD array with summary for each municipality: "
                            "locationId, municipality name, population. No parameters required."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "get_demographics",
                        "description": (
                            "Retrieve household-focused demographic data with derived statistics. "
                            "PREREQUISITE: First use find_location to get valid location IDs. "
                            "USE THIS TOOL WHEN: You specifically need household size information "
                            "or want population-to-household ratios. For general statistics "
                            "(income, unemployment, density), use get_statistics instead. "
                            "RETURNS: JSON-LD with fields: municipality, population, households, "
                            "averageHouseholdSize (calculated: population/households). "
                            "DATA SEMANTICS: Household size is derived (not raw CBS data). "
                            "EXAMPLE: For LOC001 (Amsterdam), returns avg household size of 1.88 "
                            "(872,680 people / 465,242 households)."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": (
                                        "Location identifier obtained from find_location or "
                                        "list_locations. Format: 'LOC' followed by digits."
                                    ),
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

        if tool_name == "find_location":
            query = tool_args.get("query", "")
            result = find_location(query)

            if not result.get("@graph"):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"No municipalities found matching '{query}'. "
                                    "Try searching by city name (Amsterdam, Utrecht, Rotterdam) "
                                    "or use list_locations to see all available municipalities."
                                ),
                            }
                        ],
                    },
                }

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
            }

        elif tool_name == "get_statistics":
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
