#!/usr/bin/env python3
"""
BRT Service MCP Server
======================

Data Source: Basisregistratie Topografie (BRT - pdok.nl/brt)

Purpose:
    Provides topographic map data at medium to small scales (1:10,000 and smaller)
    including geographic names, administrative boundaries, landscape features,
    and infrastructure networks for the Netherlands.

Ontology (RDF Namespace: http://example.org/geospatial#):
    - geo:GeographicName: Named geographic feature
        - geo:locationId: Links to BAG/BGT location identifiers
        - geo:nameId: BRT name identifier
        - geo:placeName: Official place name
        - geo:placeType: Classification (city/town/village/neighborhood/landmark)
        - geo:language: Name language (nl/fy for Frisian areas)

    - geo:AdministrativeBoundary: Administrative division
        - geo:locationId: Links to location
        - geo:boundaryId: BRT boundary identifier
        - geo:municipality: Municipality name (gemeente)
        - geo:province: Province name (provincie)
        - geo:waterBoard: Water board name (waterschap)
        - geo:safetyRegion: Safety region (veiligheidsregio)

    - geo:LandscapeFeature: Notable landscape element
        - geo:locationId: Links to location
        - geo:featureId: BRT feature identifier
        - geo:featureType: Type (park/forest/heath/dune/polder)
        - geo:featureName: Official name
        - geo:areaHectares: Area in hectares

Tool Discovery Pattern:
    1. Use find_place(query) to search by place name or type
    2. Get locationId from results
    3. Use get_boundaries(location_id) for administrative info

Cross-Service Linking:
    The geo:locationId is consistent across all MCP services, enabling
    combination with BAG (buildings), BGT (detailed topo), and CBS (statistics).

Response Format: JSON-LD with @context for semantic interoperability
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


def init_data():
    """Initialize BRT sample data for topographic features"""

    # Geographic names
    names = [
        # (locationId, nameId, placeName, placeType, language)
        ("LOC001", "BRT-N001", "Amsterdam", "city", "nl"),
        ("LOC001", "BRT-N002", "De Wallen", "neighborhood", "nl"),
        ("LOC001", "BRT-N003", "Dam", "landmark", "nl"),
        ("LOC002", "BRT-N004", "Utrecht", "city", "nl"),
        ("LOC002", "BRT-N005", "Binnenstad", "neighborhood", "nl"),
        ("LOC003", "BRT-N006", "Rotterdam", "city", "nl"),
        ("LOC003", "BRT-N007", "Centrum", "neighborhood", "nl"),
        ("LOC004", "BRT-N008", "Groningen", "city", "nl"),
        ("LOC004", "BRT-N009", "Grunnen", "city", "fy"),  # Gronings dialect name
        ("LOC005", "BRT-N010", "Eindhoven", "city", "nl"),
        ("LOC005", "BRT-N011", "Centrum", "neighborhood", "nl"),
    ]

    # Administrative boundaries
    boundaries = [
        # (locationId, boundaryId, municipality, province, waterBoard, safetyRegion)
        (
            "LOC001",
            "BRT-B001",
            "Amsterdam",
            "Noord-Holland",
            "Amstel, Gooi en Vecht",
            "Amsterdam-Amstelland",
        ),
        ("LOC002", "BRT-B002", "Utrecht", "Utrecht", "De Stichtse Rijnlanden", "Utrecht"),
        (
            "LOC003",
            "BRT-B003",
            "Rotterdam",
            "Zuid-Holland",
            "Hollandse Delta",
            "Rotterdam-Rijnmond",
        ),
        ("LOC004", "BRT-B004", "Groningen", "Groningen", "Noorderzijlvest", "Groningen"),
        ("LOC005", "BRT-B005", "Eindhoven", "Noord-Brabant", "De Dommel", "Brabant-Zuidoost"),
    ]

    # Landscape features
    features = [
        # (locationId, featureId, featureType, featureName, areaHectares)
        ("LOC001", "BRT-F001", "park", "Vondelpark", 47.0),
        ("LOC001", "BRT-F002", "park", "Artis", 14.0),
        ("LOC002", "BRT-F003", "park", "Park Lepelenburg", 3.5),
        ("LOC002", "BRT-F004", "forest", "Amelisweerd", 85.0),
        ("LOC003", "BRT-F005", "park", "Het Park", 26.0),
        ("LOC003", "BRT-F006", "park", "Kralingse Bos", 200.0),
        ("LOC004", "BRT-F007", "park", "Noorderplantsoen", 17.0),
        ("LOC004", "BRT-F008", "park", "Stadspark", 30.0),
        ("LOC005", "BRT-F009", "park", "Stadswandelpark", 15.0),
        ("LOC005", "BRT-F010", "forest", "Philips de Jongh Wandelpark", 22.0),
    ]

    # Add names to graph
    for loc_id, name_id, place_name, place_type, language in names:
        name_uri = URIRef(f"http://example.org/brt/names/{name_id}")

        graph.add((name_uri, RDF.type, GEO.GeographicName))
        graph.add((name_uri, GEO.locationId, Literal(loc_id)))
        graph.add((name_uri, GEO.nameId, Literal(name_id)))
        graph.add((name_uri, GEO.placeName, Literal(place_name)))
        graph.add((name_uri, GEO.placeType, Literal(place_type)))
        graph.add((name_uri, GEO.language, Literal(language)))

    # Add boundaries to graph
    for loc_id, bound_id, municipality, province, water_board, safety_region in boundaries:
        boundary_uri = URIRef(f"http://example.org/brt/boundaries/{bound_id}")

        graph.add((boundary_uri, RDF.type, GEO.AdministrativeBoundary))
        graph.add((boundary_uri, GEO.locationId, Literal(loc_id)))
        graph.add((boundary_uri, GEO.boundaryId, Literal(bound_id)))
        graph.add((boundary_uri, GEO.municipality, Literal(municipality)))
        graph.add((boundary_uri, GEO.province, Literal(province)))
        graph.add((boundary_uri, GEO.waterBoard, Literal(water_board)))
        graph.add((boundary_uri, GEO.safetyRegion, Literal(safety_region)))

    # Add landscape features to graph
    for loc_id, feature_id, feature_type, feature_name, area in features:
        feature_uri = URIRef(f"http://example.org/brt/features/{feature_id}")

        graph.add((feature_uri, RDF.type, GEO.LandscapeFeature))
        graph.add((feature_uri, GEO.locationId, Literal(loc_id)))
        graph.add((feature_uri, GEO.featureId, Literal(feature_id)))
        graph.add((feature_uri, GEO.featureType, Literal(feature_type)))
        graph.add((feature_uri, GEO.featureName, Literal(feature_name)))
        graph.add((feature_uri, GEO.areaHectares, Literal(area, datatype=XSD.decimal)))


init_data()


def find_place(query):
    """Find places by name, type, or location ID"""
    query_lower = query.lower()
    results = []

    # Search in geographic names
    for name_uri in graph.subjects(RDF.type, GEO.GeographicName):
        loc_id = str(graph.value(name_uri, GEO.locationId))
        place_name = str(graph.value(name_uri, GEO.placeName))
        place_type = str(graph.value(name_uri, GEO.placeType))

        if (
            query_lower in loc_id.lower()
            or query_lower in place_name.lower()
            or query_lower in place_type.lower()
        ):
            results.append(
                {
                    "@type": "geo:GeographicName",
                    "geo:locationId": loc_id,
                    "geo:nameId": str(graph.value(name_uri, GEO.nameId)),
                    "geo:placeName": place_name,
                    "geo:placeType": place_type,
                    "geo:language": str(graph.value(name_uri, GEO.language)),
                }
            )

    # Search in landscape features
    for feature_uri in graph.subjects(RDF.type, GEO.LandscapeFeature):
        loc_id = str(graph.value(feature_uri, GEO.locationId))
        feature_name = str(graph.value(feature_uri, GEO.featureName))
        feature_type = str(graph.value(feature_uri, GEO.featureType))

        if (
            query_lower in loc_id.lower()
            or query_lower in feature_name.lower()
            or query_lower in feature_type.lower()
        ):
            results.append(
                {
                    "@type": "geo:LandscapeFeature",
                    "geo:locationId": loc_id,
                    "geo:featureId": str(graph.value(feature_uri, GEO.featureId)),
                    "geo:featureName": feature_name,
                    "geo:featureType": feature_type,
                }
            )

    return {"@context": {"geo": "http://example.org/geospatial#"}, "@graph": results}


def get_boundaries(location_id):
    """Get administrative boundary information for a location"""
    boundary_uri = None
    for boundary in graph.subjects(RDF.type, GEO.AdministrativeBoundary):
        if str(graph.value(boundary, GEO.locationId)) == location_id:
            boundary_uri = boundary
            break

    if not boundary_uri:
        return None

    return {
        "@context": {"geo": "http://example.org/geospatial#"},
        "@id": str(boundary_uri),
        "@type": "geo:AdministrativeBoundary",
        "geo:locationId": location_id,
        "geo:boundaryId": str(graph.value(boundary_uri, GEO.boundaryId)),
        "geo:municipality": str(graph.value(boundary_uri, GEO.municipality)),
        "geo:province": str(graph.value(boundary_uri, GEO.province)),
        "geo:waterBoard": str(graph.value(boundary_uri, GEO.waterBoard)),
        "geo:safetyRegion": str(graph.value(boundary_uri, GEO.safetyRegion)),
    }


def get_place_names(location_id):
    """Get all geographic names for a location"""
    names = []

    for name_uri in graph.subjects(RDF.type, GEO.GeographicName):
        if str(graph.value(name_uri, GEO.locationId)) == location_id:
            names.append(
                {
                    "@type": "geo:GeographicName",
                    "geo:nameId": str(graph.value(name_uri, GEO.nameId)),
                    "geo:placeName": str(graph.value(name_uri, GEO.placeName)),
                    "geo:placeType": str(graph.value(name_uri, GEO.placeType)),
                    "geo:language": str(graph.value(name_uri, GEO.language)),
                }
            )

    if not names:
        return None

    return {
        "@context": {"geo": "http://example.org/geospatial#"},
        "geo:locationId": location_id,
        "@graph": names,
    }


def get_landscape(location_id):
    """Get landscape features for a location"""
    features = []

    for feature_uri in graph.subjects(RDF.type, GEO.LandscapeFeature):
        if str(graph.value(feature_uri, GEO.locationId)) == location_id:
            features.append(
                {
                    "@type": "geo:LandscapeFeature",
                    "geo:featureId": str(graph.value(feature_uri, GEO.featureId)),
                    "geo:featureName": str(graph.value(feature_uri, GEO.featureName)),
                    "geo:featureType": str(graph.value(feature_uri, GEO.featureType)),
                    "geo:areaHectares": str(graph.value(feature_uri, GEO.areaHectares)),
                }
            )

    if not features:
        return None

    return {
        "@context": {"geo": "http://example.org/geospatial#"},
        "geo:locationId": location_id,
        "@graph": features,
    }


def list_municipalities():
    """List all municipalities with their administrative info"""
    municipalities = []

    for boundary_uri in graph.subjects(RDF.type, GEO.AdministrativeBoundary):
        municipalities.append(
            {
                "@type": "geo:AdministrativeBoundary",
                "geo:locationId": str(graph.value(boundary_uri, GEO.locationId)),
                "geo:municipality": str(graph.value(boundary_uri, GEO.municipality)),
                "geo:province": str(graph.value(boundary_uri, GEO.province)),
            }
        )

    return {"@context": {"geo": "http://example.org/geospatial#"}, "@graph": municipalities}


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
                    "name": "brt-service",
                    "version": "1.0.0",
                    "description": (
                        "BRT (Basisregistratie Topografie) MCP Server. "
                        "Provides topographic map data at 1:10,000 and smaller scales "
                        "including place names, administrative boundaries, and landscape "
                        "features. Data source: Kadaster/PDOK BRT (pdok.nl/brt). "
                        "Use this service for questions about: place names, neighborhoods, "
                        "provinces, municipalities, water boards, safety regions, "
                        "parks, forests, and other landscape features."
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
                        "name": "find_place",
                        "description": (
                            "Search for places by name, type, or location ID. "
                            "USE THIS to discover locations and geographic features. "
                            "Searches place names, neighborhoods, landmarks, parks, forests. "
                            "EXAMPLE: find_place('Amsterdam') returns Amsterdam and its "
                            "neighborhoods. EXAMPLE: find_place('park') returns all parks. "
                            "Returns locationId values for use with other tools."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": (
                                        "Search term: place name, location ID, or type "
                                        "(city/neighborhood/landmark/park/forest)."
                                    ),
                                }
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_boundaries",
                        "description": (
                            "Get administrative boundary information for a location. "
                            "RETURNS: Municipality (gemeente), province (provincie), "
                            "water board (waterschap), and safety region (veiligheidsregio). "
                            "USE FOR: Understanding which authorities have jurisdiction "
                            "over a location, or finding administrative hierarchy."
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
                        "name": "get_place_names",
                        "description": (
                            "Get all geographic names associated with a location. "
                            "RETURNS: City name, neighborhood names, landmarks, with "
                            "language codes (nl for Dutch, fy for Frisian). "
                            "USE FOR: Finding official names for places, or discovering "
                            "what neighborhoods are in an area."
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
                        "name": "get_landscape",
                        "description": (
                            "Get landscape features (parks, forests, etc.) near a location. "
                            "RETURNS: Feature name, type (park/forest/heath/dune/polder), "
                            "and area in hectares. "
                            "USE FOR: Finding green spaces, natural areas, or recreational "
                            "areas near a location."
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
                        "name": "list_municipalities",
                        "description": (
                            "List all municipalities in the database with their provinces. "
                            "USE THIS for an overview of available locations or to see "
                            "what areas are covered. No parameters required."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "find_place":
            query = tool_args.get("query", "")
            result = find_place(query)

            if not result.get("@graph"):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"No places found matching '{query}'. "
                                    "Try searching by city name, neighborhood, or feature type "
                                    "(e.g., 'park', 'city', 'neighborhood')."
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

        elif tool_name == "get_boundaries":
            location_id = tool_args.get("location_id")
            result = get_boundaries(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No boundary data found for location {location_id}",
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

        elif tool_name == "get_place_names":
            location_id = tool_args.get("location_id")
            result = get_place_names(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No place names found for location {location_id}",
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

        elif tool_name == "get_landscape":
            location_id = tool_args.get("location_id")
            result = get_landscape(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No landscape features found for location {location_id}",
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

        elif tool_name == "list_municipalities":
            result = list_municipalities()
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
