#!/usr/bin/env python3
"""
Rijkswaterstaat Service MCP Server
==================================

Data Source: Rijkswaterstaat (Dutch Ministry of Infrastructure and Water Management -
rijkswaterstaat.nl)

Purpose:
    Provides data on Dutch national infrastructure including highways (Rijkswegen),
    bridges, tunnels, locks, canals, rivers, and water level measurements.

Ontology (RDF Namespace: http://imx-geo-prime.org/geospatial#):
    - geo:Location: Geographic location with administrative data
        - geo:locationId: Unique identifier (e.g., "LOC001")
        - geo:municipality: Municipality/city name
        - geo:province: Dutch province (Noord-Holland, Utrecht, Zuid-Holland, etc.)

    - geo:Infrastructure: Physical infrastructure objects
        - geo:locationId: Links to corresponding Location
        - geo:infrastructureType: Type classification (bridge/tunnel/lock)
        - geo:condition: Maintenance status (good/fair/poor)
        - geo:managedBy: Responsible organization
        - rdfs:label: Descriptive name (e.g., "IJ-tunnel entrance")

    - geo:WaterBody: Water features (canals, rivers)
        - geo:locationId: Links to corresponding Location
        - geo:waterType: Classification (canal/river)
        - geo:waterLevel: Height in meters relative to NAP (xsd:decimal)
        - geo:managedBy: Water authority (Rijkswaterstaat/Waternet/Hoogheemraadschap)
        - rdfs:label: Name of water body

    - geo:Road: Highway/road data
        - geo:locationId: Links to corresponding Location
        - geo:roadType: Classification (highway)
        - geo:roadNumber: Official designation (e.g., "A10", "A12")
        - geo:maxSpeed: Speed limit in km/h (xsd:integer)
        - geo:condition: Maintenance status (good/fair/poor)

Reference Datum:
    NAP (Normaal Amsterdams Peil) = Dutch vertical reference datum
    - 0 = approximate sea level at Amsterdam
    - Positive values = above sea level
    - Negative values = below sea level (common in polders and river deltas)

Tool Discovery Pattern:
    1. Use find_location(query) to search by municipality or province
    2. Get locationId from results (also shows infrastructure/water counts)
    3. Use get_infrastructure(location_id) for complete overview, or
       get_water_level(location_id) for water-specific data

Cross-Service Linking:
    The geo:locationId is consistent across all MCP services (Kadaster, CBS,
    Rijkswaterstaat), enabling queries that combine property data, statistics,
    and infrastructure for the same geographic location.

Response Format: JSON-LD with @context for semantic interoperability
"""

import json
import sys

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

# Define namespace
GEO = Namespace("http://imx-geo-prime.org/geospatial#")

# Initialize in-memory RDF graph
graph = Graph()
graph.bind("geo", GEO)


# Add sample Rijkswaterstaat data (infrastructure and water management)
def init_data():
    # Locations with their metadata (for find_location tool)
    locations = [
        # (locationId, municipality, province)
        ("LOC001", "Amsterdam", "Noord-Holland"),
        ("LOC002", "Utrecht", "Utrecht"),
        ("LOC003", "Rotterdam", "Zuid-Holland"),
    ]

    for loc_id, municipality, province in locations:
        location_uri = URIRef(f"http://imx-geo-prime.org/locations/{loc_id}")
        graph.add((location_uri, RDF.type, GEO.Location))
        graph.add((location_uri, GEO.locationId, Literal(loc_id)))
        graph.add((location_uri, GEO.municipality, Literal(municipality)))
        graph.add((location_uri, GEO.province, Literal(province)))

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
        infra_uri = URIRef(f"http://imx-geo-prime.org/infrastructure/{infra_id}")

        graph.add((infra_uri, RDF.type, GEO.Infrastructure))
        graph.add((infra_uri, GEO.locationId, Literal(loc_id)))
        graph.add((infra_uri, GEO.infrastructureType, Literal(infra_type)))
        graph.add((infra_uri, GEO.condition, Literal(condition)))
        graph.add((infra_uri, GEO.managedBy, Literal(managed)))
        graph.add((infra_uri, RDFS.label, Literal(description)))

    for loc_id, water_id, water_type, level, managed, name in water_bodies:
        water_uri = URIRef(f"http://imx-geo-prime.org/water/{water_id}")

        graph.add((water_uri, RDF.type, GEO.WaterBody))
        graph.add((water_uri, GEO.locationId, Literal(loc_id)))
        graph.add((water_uri, GEO.waterType, Literal(water_type)))
        graph.add((water_uri, GEO.waterLevel, Literal(level, datatype=XSD.decimal)))
        graph.add((water_uri, GEO.managedBy, Literal(managed)))
        graph.add((water_uri, RDFS.label, Literal(name)))

    for loc_id, road_id, road_type, road_num, max_speed, condition in roads:
        road_uri = URIRef(f"http://imx-geo-prime.org/roads/{road_id}")

        graph.add((road_uri, RDF.type, GEO.Road))
        graph.add((road_uri, GEO.locationId, Literal(loc_id)))
        graph.add((road_uri, GEO.roadType, Literal(road_type)))
        graph.add((road_uri, GEO.roadNumber, Literal(road_num)))
        graph.add((road_uri, GEO.maxSpeed, Literal(max_speed, datatype=XSD.integer)))
        graph.add((road_uri, GEO.condition, Literal(condition)))


init_data()


def find_location(query):
    """Find locations by searching municipality name, province, or location ID"""
    query_lower = query.lower()
    results = []

    for location_uri in graph.subjects(RDF.type, GEO.Location):
        loc_id = str(graph.value(location_uri, GEO.locationId))
        municipality = str(graph.value(location_uri, GEO.municipality))
        province = str(graph.value(location_uri, GEO.province))

        # Search in municipality, province, and location ID
        if (
            query_lower in municipality.lower()
            or query_lower in province.lower()
            or query_lower in loc_id.lower()
        ):
            # Get infrastructure summary for this location
            infra_count = sum(
                1
                for uri in graph.subjects(RDF.type, GEO.Infrastructure)
                if str(graph.value(uri, GEO.locationId)) == loc_id
            )
            water_count = sum(
                1
                for uri in graph.subjects(RDF.type, GEO.WaterBody)
                if str(graph.value(uri, GEO.locationId)) == loc_id
            )

            results.append(
                {
                    "@type": "geo:Location",
                    "geo:locationId": loc_id,
                    "geo:municipality": municipality,
                    "geo:province": province,
                    "summary:infrastructureCount": infra_count,
                    "summary:waterBodyCount": water_count,
                }
            )

    return {"@context": {"geo": "http://imx-geo-prime.org/geospatial#"}, "@graph": results}


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
            "geo": "http://imx-geo-prime.org/geospatial#",
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

    return {"@context": {"geo": "http://imx-geo-prime.org/geospatial#"}, "@graph": roads}


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
                    "geo": "http://imx-geo-prime.org/geospatial#",
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
                "serverInfo": {
                    "name": "rijkswaterstaat-service",
                    "version": "1.0.0",
                    "description": (
                        "Rijkswaterstaat (Dutch Ministry of Infrastructure and Water Management) "
                        "MCP Server. Provides data on national infrastructure including highways, "
                        "bridges, tunnels, locks, canals, rivers, and water levels. "
                        "Data source: Rijkswaterstaat (rijkswaterstaat.nl). "
                        "Use this service for questions about: roads and highways, bridges and "
                        "tunnels, water bodies (canals, rivers), water levels, infrastructure "
                        "condition, and which organization manages specific infrastructure."
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
                            "Search for locations by municipality name or province to get their "
                            "location identifiers and infrastructure summary. "
                            "USE THIS TOOL FIRST when you don't know the location ID. "
                            "This is the discovery tool for the Rijkswaterstaat database. "
                            "WORKFLOW: Call find_location('Amsterdam') to get LOC001 and see "
                            "what infrastructure exists, then use that ID with get_infrastructure "
                            "or get_water_level for details. "
                            "RETURNS: JSON-LD array of matching locations with: locationId, "
                            "municipality, province, infrastructureCount, waterBodyCount. "
                            "SEARCH EXAMPLES: 'Amsterdam' returns LOC001 (Noord-Holland), "
                            "'Utrecht' returns LOC002, 'Zuid-Holland' returns Rotterdam (LOC003). "
                            "Partial matches work: 'dam' matches Amsterdam."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": (
                                        "Search term: municipality/city name (e.g., 'Amsterdam'), "
                                        "province name (e.g., 'Noord-Holland'), or partial name. "
                                        "Case-insensitive partial matching."
                                    ),
                                }
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_infrastructure",
                        "description": (
                            "Retrieve ALL infrastructure data for a location: roads, bridges, "
                            "tunnels, locks, AND water bodies. Most comprehensive tool. "
                            "PREREQUISITE: First use find_location to get valid location IDs. "
                            "USE THIS TOOL WHEN: You need a complete infrastructure overview, "
                            "want to know what bridges/tunnels exist, or need combined road and "
                            "water data for a location. "
                            "RETURNS: JSON-LD with three types of objects: "
                            "(1) Infrastructure: infrastructureType (bridge/tunnel/lock), "
                            "condition (good/fair/poor), managedBy (responsible organization), "
                            "label (descriptive name). "
                            "(2) WaterBody: waterType (canal/river), waterLevel (meters relative "
                            "to NAP - Normaal Amsterdams Peil, Dutch reference datum), managedBy, "
                            "label. "
                            "(3) Road: roadType, roadNumber (e.g., A10), maxSpeed, condition. "
                            "DATA SEMANTICS: All objects linked via geo:locationId. Water levels "
                            "use NAP (0 = sea level at Amsterdam). "
                            "EXAMPLE: LOC001 returns IJ-tunnel (bridge), Damrak canal, A10."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": (
                                        "Location identifier obtained from find_location. "
                                        "Format: 'LOC' followed by digits (e.g., 'LOC001')."
                                    ),
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                    {
                        "name": "list_roads",
                        "description": (
                            "List ALL national highways (Rijkswegen) in the database. "
                            "USE THIS TOOL WHEN: You need to compare roads across locations, "
                            "want road numbers and conditions, or need a roads-only overview "
                            "without knowing specific locations. "
                            "ALTERNATIVE TO: find_location + get_infrastructure (use this when "
                            "you only care about roads and want all of them). "
                            "RETURNS: JSON-LD array with each road: locationId, roadNumber "
                            "(e.g., A10, A12, A15), roadType, condition. No parameters required."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "get_water_level",
                        "description": (
                            "Retrieve current water level measurement for a specific water body. "
                            "PREREQUISITE: First use find_location to get valid location IDs. "
                            "USE THIS TOOL WHEN: You specifically need water level data, flood "
                            "risk assessment, or water management information. For complete "
                            "infrastructure including roads and bridges, use get_infrastructure. "
                            "RETURNS: JSON-LD with: waterType (canal/river), waterLevel "
                            "(meters relative to NAP, where 0 = sea level), managedBy "
                            "(Rijkswaterstaat, Waternet, or Hoogheemraadschap), label. "
                            "DATA SEMANTICS: NAP is the Dutch vertical reference datum. "
                            "Negative values common in river deltas and polders. "
                            "EXAMPLE: LOC003 (Rotterdam) Nieuwe Maas river shows -0.2m (below "
                            "sea level, typical for river deltas in the Netherlands)."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": (
                                        "Location identifier obtained from find_location. "
                                        "Format: 'LOC' followed by digits."
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
                                    f"No locations found matching '{query}'. "
                                    "Try searching by city name (Amsterdam, Utrecht, Rotterdam) "
                                    "or province (Noord-Holland, Utrecht, Zuid-Holland)."
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

        elif tool_name == "get_infrastructure":
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
