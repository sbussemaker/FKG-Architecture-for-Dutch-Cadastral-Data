#!/usr/bin/env python3
"""
BGT Service MCP Server
======================

Data Source: Basisregistratie Grootschalige Topografie (BGT - pdok.nl/bgt)

Purpose:
    Provides large-scale topographic data (1:500 to 1:5000) including roads,
    water bodies, land use parcels, vegetation areas, and terrain classifications
    for locations in the Netherlands.

Ontology (RDF Namespace: http://imx-geo-prime.org/geospatial#):
    - geo:TopographicArea: A classified land area
        - geo:locationId: Links to BAG/BRT location identifiers
        - geo:areaId: BGT area identifier
        - geo:areaType: Classification (road/water/vegetation/building/terrain)
        - geo:surfaceType: Surface material (asphalt/grass/water/concrete/etc.)
        - geo:managedBy: Organization responsible for maintenance

    - geo:Road: Road segment information
        - geo:locationId: Links to location
        - geo:roadId: BGT road identifier
        - geo:roadType: Classification (highway/regional/local/cycleway/footpath)
        - geo:surfaceType: Road surface (asphalt/brick/gravel)
        - geo:roadName: Official road name
        - geo:managedBy: Road authority

    - geo:WaterBody: Water feature information
        - geo:locationId: Links to location
        - geo:waterId: BGT water identifier
        - geo:waterType: Classification (river/canal/lake/sea/ditch)
        - geo:waterName: Official water name
        - geo:managedBy: Water authority (often Rijkswaterstaat or waterschap)

Tool Discovery Pattern:
    1. Use find_area(query) to search by location name or type
    2. Get locationId from results
    3. Use get_terrain(location_id) for detailed topographic info

Cross-Service Linking:
    The geo:locationId is consistent across all MCP services, enabling
    combination with BAG (buildings), BRT (maps), and CBS (statistics).

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


def init_data():
    """Initialize BGT sample data for topographic features"""

    # Topographic areas linked to locations
    areas = [
        # (locationId, areaId, areaType, surfaceType, managedBy, areaSize)
        ("LOC001", "BGT-A001", "mixed_urban", "paved", "Gemeente Amsterdam", 2500.0),
        ("LOC002", "BGT-A002", "urban_center", "brick", "Gemeente Utrecht", 1800.0),
        ("LOC003", "BGT-A003", "civic_square", "concrete", "Gemeente Rotterdam", 5000.0),
        ("LOC004", "BGT-A004", "market_square", "brick", "Gemeente Groningen", 3200.0),
        ("LOC005", "BGT-A005", "residential", "mixed", "Gemeente Eindhoven", 800.0),
    ]

    # Roads near locations
    roads = [
        # (locationId, roadId, roadType, surfaceType, roadName, managedBy)
        ("LOC001", "BGT-R001", "local", "asphalt", "Damrak", "Gemeente Amsterdam"),
        ("LOC001", "BGT-R002", "cycleway", "asphalt", "Damrak fietspad", "Gemeente Amsterdam"),
        ("LOC002", "BGT-R003", "local", "brick", "Oudegracht", "Gemeente Utrecht"),
        ("LOC003", "BGT-R004", "regional", "asphalt", "Coolsingel", "Gemeente Rotterdam"),
        ("LOC003", "BGT-R005", "tram_track", "rail", "Coolsingel tramlijn", "RET"),
        ("LOC004", "BGT-R006", "pedestrian", "brick", "Grote Markt", "Gemeente Groningen"),
    ]

    # Water bodies near locations
    water_bodies = [
        # (locationId, waterId, waterType, waterName, managedBy, width)
        ("LOC001", "BGT-W001", "canal", "Damrak (water)", "Waternet", 25.0),
        (
            "LOC002",
            "BGT-W002",
            "canal",
            "Oudegracht",
            "Hoogheemraadschap De Stichtse Rijnlanden",
            12.0,
        ),
        ("LOC003", "BGT-W003", "river", "Nieuwe Maas", "Rijkswaterstaat", 350.0),
        ("LOC004", "BGT-W004", "canal", "Hoornsediep", "Waterschap Noorderzijlvest", 15.0),
    ]

    # Add areas to graph
    for loc_id, area_id, area_type, surface, managed_by, area_size in areas:
        area_uri = URIRef(f"http://imx-geo-prime.org/bgt/areas/{area_id}")

        graph.add((area_uri, RDF.type, GEO.TopographicArea))
        graph.add((area_uri, GEO.locationId, Literal(loc_id)))
        graph.add((area_uri, GEO.areaId, Literal(area_id)))
        graph.add((area_uri, GEO.areaType, Literal(area_type)))
        graph.add((area_uri, GEO.surfaceType, Literal(surface)))
        graph.add((area_uri, GEO.managedBy, Literal(managed_by)))
        graph.add((area_uri, GEO.areaSize, Literal(area_size, datatype=XSD.decimal)))

    # Add roads to graph
    for loc_id, road_id, road_type, surface, road_name, managed_by in roads:
        road_uri = URIRef(f"http://imx-geo-prime.org/bgt/roads/{road_id}")

        graph.add((road_uri, RDF.type, GEO.Road))
        graph.add((road_uri, GEO.locationId, Literal(loc_id)))
        graph.add((road_uri, GEO.roadId, Literal(road_id)))
        graph.add((road_uri, GEO.roadType, Literal(road_type)))
        graph.add((road_uri, GEO.surfaceType, Literal(surface)))
        graph.add((road_uri, GEO.roadName, Literal(road_name)))
        graph.add((road_uri, GEO.managedBy, Literal(managed_by)))

    # Add water bodies to graph
    for loc_id, water_id, water_type, water_name, managed_by, width in water_bodies:
        water_uri = URIRef(f"http://imx-geo-prime.org/bgt/water/{water_id}")

        graph.add((water_uri, RDF.type, GEO.WaterBody))
        graph.add((water_uri, GEO.locationId, Literal(loc_id)))
        graph.add((water_uri, GEO.waterId, Literal(water_id)))
        graph.add((water_uri, GEO.waterType, Literal(water_type)))
        graph.add((water_uri, GEO.waterName, Literal(water_name)))
        graph.add((water_uri, GEO.managedBy, Literal(managed_by)))
        graph.add((water_uri, GEO.width, Literal(width, datatype=XSD.decimal)))


init_data()


def find_area(query):
    """Find topographic areas by location name, area type, or feature name"""
    query_lower = query.lower()
    results = []

    # Search in areas
    for area_uri in graph.subjects(RDF.type, GEO.TopographicArea):
        loc_id = str(graph.value(area_uri, GEO.locationId))
        area_type = str(graph.value(area_uri, GEO.areaType))
        managed_by = str(graph.value(area_uri, GEO.managedBy))

        if (
            query_lower in loc_id.lower()
            or query_lower in area_type.lower()
            or query_lower in managed_by.lower()
        ):
            results.append(
                {
                    "@type": "geo:TopographicArea",
                    "geo:locationId": loc_id,
                    "geo:areaId": str(graph.value(area_uri, GEO.areaId)),
                    "geo:areaType": area_type,
                    "geo:surfaceType": str(graph.value(area_uri, GEO.surfaceType)),
                    "geo:managedBy": managed_by,
                }
            )

    # Search in roads
    for road_uri in graph.subjects(RDF.type, GEO.Road):
        loc_id = str(graph.value(road_uri, GEO.locationId))
        road_name = str(graph.value(road_uri, GEO.roadName))
        road_type = str(graph.value(road_uri, GEO.roadType))

        if (
            query_lower in loc_id.lower()
            or query_lower in road_name.lower()
            or query_lower in road_type.lower()
        ):
            results.append(
                {
                    "@type": "geo:Road",
                    "geo:locationId": loc_id,
                    "geo:roadId": str(graph.value(road_uri, GEO.roadId)),
                    "geo:roadName": road_name,
                    "geo:roadType": road_type,
                }
            )

    # Search in water bodies
    for water_uri in graph.subjects(RDF.type, GEO.WaterBody):
        loc_id = str(graph.value(water_uri, GEO.locationId))
        water_name = str(graph.value(water_uri, GEO.waterName))
        water_type = str(graph.value(water_uri, GEO.waterType))

        if (
            query_lower in loc_id.lower()
            or query_lower in water_name.lower()
            or query_lower in water_type.lower()
        ):
            results.append(
                {
                    "@type": "geo:WaterBody",
                    "geo:locationId": loc_id,
                    "geo:waterId": str(graph.value(water_uri, GEO.waterId)),
                    "geo:waterName": water_name,
                    "geo:waterType": water_type,
                }
            )

    return {"@context": {"geo": "http://imx-geo-prime.org/geospatial#"}, "@graph": results}


def get_terrain(location_id):
    """Get all topographic features for a location"""
    features = {
        "@context": {"geo": "http://imx-geo-prime.org/geospatial#"},
        "geo:locationId": location_id,
        "areas": [],
        "roads": [],
        "waterBodies": [],
    }

    found_any = False

    # Get area info
    for area_uri in graph.subjects(RDF.type, GEO.TopographicArea):
        if str(graph.value(area_uri, GEO.locationId)) == location_id:
            found_any = True
            features["areas"].append(
                {
                    "@type": "geo:TopographicArea",
                    "geo:areaId": str(graph.value(area_uri, GEO.areaId)),
                    "geo:areaType": str(graph.value(area_uri, GEO.areaType)),
                    "geo:surfaceType": str(graph.value(area_uri, GEO.surfaceType)),
                    "geo:managedBy": str(graph.value(area_uri, GEO.managedBy)),
                    "geo:areaSize": str(graph.value(area_uri, GEO.areaSize)),
                }
            )

    # Get roads
    for road_uri in graph.subjects(RDF.type, GEO.Road):
        if str(graph.value(road_uri, GEO.locationId)) == location_id:
            found_any = True
            features["roads"].append(
                {
                    "@type": "geo:Road",
                    "geo:roadId": str(graph.value(road_uri, GEO.roadId)),
                    "geo:roadName": str(graph.value(road_uri, GEO.roadName)),
                    "geo:roadType": str(graph.value(road_uri, GEO.roadType)),
                    "geo:surfaceType": str(graph.value(road_uri, GEO.surfaceType)),
                    "geo:managedBy": str(graph.value(road_uri, GEO.managedBy)),
                }
            )

    # Get water bodies
    for water_uri in graph.subjects(RDF.type, GEO.WaterBody):
        if str(graph.value(water_uri, GEO.locationId)) == location_id:
            found_any = True
            features["waterBodies"].append(
                {
                    "@type": "geo:WaterBody",
                    "geo:waterId": str(graph.value(water_uri, GEO.waterId)),
                    "geo:waterName": str(graph.value(water_uri, GEO.waterName)),
                    "geo:waterType": str(graph.value(water_uri, GEO.waterType)),
                    "geo:managedBy": str(graph.value(water_uri, GEO.managedBy)),
                    "geo:width": str(graph.value(water_uri, GEO.width)),
                }
            )

    return features if found_any else None


def get_roads(location_id):
    """Get road information for a location"""
    roads = []

    for road_uri in graph.subjects(RDF.type, GEO.Road):
        if str(graph.value(road_uri, GEO.locationId)) == location_id:
            roads.append(
                {
                    "@type": "geo:Road",
                    "geo:roadId": str(graph.value(road_uri, GEO.roadId)),
                    "geo:roadName": str(graph.value(road_uri, GEO.roadName)),
                    "geo:roadType": str(graph.value(road_uri, GEO.roadType)),
                    "geo:surfaceType": str(graph.value(road_uri, GEO.surfaceType)),
                    "geo:managedBy": str(graph.value(road_uri, GEO.managedBy)),
                }
            )

    if not roads:
        return None

    return {
        "@context": {"geo": "http://imx-geo-prime.org/geospatial#"},
        "geo:locationId": location_id,
        "@graph": roads,
    }


def get_water(location_id):
    """Get water body information for a location"""
    water_bodies = []

    for water_uri in graph.subjects(RDF.type, GEO.WaterBody):
        if str(graph.value(water_uri, GEO.locationId)) == location_id:
            water_bodies.append(
                {
                    "@type": "geo:WaterBody",
                    "geo:waterId": str(graph.value(water_uri, GEO.waterId)),
                    "geo:waterName": str(graph.value(water_uri, GEO.waterName)),
                    "geo:waterType": str(graph.value(water_uri, GEO.waterType)),
                    "geo:managedBy": str(graph.value(water_uri, GEO.managedBy)),
                    "geo:width": str(graph.value(water_uri, GEO.width)),
                }
            )

    if not water_bodies:
        return None

    return {
        "@context": {"geo": "http://imx-geo-prime.org/geospatial#"},
        "geo:locationId": location_id,
        "@graph": water_bodies,
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
                    "name": "bgt-service",
                    "version": "1.0.0",
                    "description": (
                        "BGT (Basisregistratie Grootschalige Topografie) MCP Server. "
                        "Provides large-scale topographic data (1:500-1:5000) including "
                        "roads, water bodies, terrain types, and land use. "
                        "Data source: Kadaster/PDOK BGT (pdok.nl/bgt). "
                        "Use this service for questions about: road types and surfaces, "
                        "water features (canals, rivers), terrain classification, "
                        "land use, and infrastructure management authorities."
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
                        "name": "find_area",
                        "description": (
                            "Search for topographic features by location ID, feature name, "
                            "or type. USE THIS to discover what BGT data is available. "
                            "Searches across areas, roads, and water bodies. "
                            "EXAMPLE: find_area('canal') finds all canals. "
                            "EXAMPLE: find_area('LOC001') finds all features near that location. "
                            "Returns locationId values usable with other tools."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": (
                                        "Search term: location ID (e.g., 'LOC001'), feature name "
                                        "(e.g., 'Oudegracht'), or type (e.g., 'canal', 'cycleway')."
                                    ),
                                }
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_terrain",
                        "description": (
                            "Get complete topographic information for a location including "
                            "terrain type, roads, and water bodies. "
                            "PREREQUISITE: Get locationId from BAG find_address or BGT find_area. "
                            "RETURNS: All BGT features at that location - areas with surface "
                            "types, roads with classifications, water bodies with types. "
                            "USE FOR: Understanding the physical environment of a location."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": "Location identifier (e.g., 'LOC001').",
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                    {
                        "name": "get_roads",
                        "description": (
                            "Get road infrastructure information for a location. "
                            "RETURNS: Road names, types (highway/local/cycleway/footpath), "
                            "surface materials, and managing authorities. "
                            "USE FOR: Questions about road access, cycling infrastructure, "
                            "or who maintains the roads."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": "Location identifier (e.g., 'LOC001').",
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                    {
                        "name": "get_water",
                        "description": (
                            "Get water body information for a location. "
                            "RETURNS: Water feature names, types (river/canal/lake), "
                            "widths, and managing water authorities. "
                            "USE FOR: Questions about nearby water, flood risk context, "
                            "or water management responsibilities."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": "Location identifier (e.g., 'LOC001').",
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

        if tool_name == "find_area":
            query = tool_args.get("query", "")
            result = find_area(query)

            if not result.get("@graph"):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"No topographic features found matching '{query}'. "
                                    "Try searching by location ID, feature name, or type "
                                    "(e.g., 'canal', 'cycleway', 'LOC001')."
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

        elif tool_name == "get_terrain":
            location_id = tool_args.get("location_id")
            result = get_terrain(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No topographic data found for location {location_id}",
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

        elif tool_name == "get_roads":
            location_id = tool_args.get("location_id")
            result = get_roads(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No road data found for location {location_id}",
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

        elif tool_name == "get_water":
            location_id = tool_args.get("location_id")
            result = get_water(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No water body data found for location {location_id}",
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
