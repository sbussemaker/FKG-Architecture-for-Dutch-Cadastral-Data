#!/usr/bin/env python3
"""
Kadaster Service MCP Server
Dutch Land Registry - Cadastral data, property boundaries, and ownership information
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


# Add sample Kadaster data (property ownership and cadastral information)
def init_data():
    properties = [
        # (locationId, cadastralId, address, postalCode, municipality, owner,
        #  surfaceArea, landUse, buildingType, constructionYear)
        (
            "LOC001",
            "AMS01-G-1234",
            "Damrak 1",
            "1012 LG",
            "Amsterdam",
            "Gemeente Amsterdam",
            450.5,
            "commercial",
            "office",
            1920,
        ),
        (
            "LOC002",
            "UTR02-K-5678",
            "Oudegracht 231",
            "3511 NK",
            "Utrecht",
            "Universiteit Utrecht",
            320.0,
            "educational",
            "university",
            1636,
        ),
        (
            "LOC003",
            "RTD03-A-9012",
            "Coolsingel 40",
            "3011 AD",
            "Rotterdam",
            "Gemeente Rotterdam",
            1200.0,
            "government",
            "municipal_building",
            1914,
        ),
    ]

    for (
        loc_id,
        cadastral_id,
        address,
        postal,
        municipality,
        owner,
        surface,
        land_use,
        building_type,
        year,
    ) in properties:
        location_uri = URIRef(f"http://example.org/locations/{loc_id}")
        property_uri = URIRef(f"http://example.org/properties/{cadastral_id}")

        # Location data
        graph.add((location_uri, RDF.type, GEO.Location))
        graph.add((location_uri, GEO.locationId, Literal(loc_id)))
        graph.add((location_uri, GEO.address, Literal(address)))
        graph.add((location_uri, GEO.postalCode, Literal(postal)))
        graph.add((location_uri, GEO.municipality, Literal(municipality)))

        # Property/Cadastral data
        graph.add((property_uri, RDF.type, GEO.Property))
        graph.add((property_uri, GEO.cadastralId, Literal(cadastral_id)))
        graph.add((property_uri, GEO.locationId, Literal(loc_id)))
        graph.add((property_uri, GEO.owner, Literal(owner)))
        graph.add((property_uri, GEO.surfaceArea, Literal(surface, datatype=XSD.decimal)))
        graph.add((property_uri, GEO.landUse, Literal(land_use)))
        graph.add((property_uri, GEO.buildingType, Literal(building_type)))
        graph.add((property_uri, GEO.constructionYear, Literal(year, datatype=XSD.integer)))


init_data()


def get_property(location_id):
    """Get cadastral property data by location ID"""
    location_uri = URIRef(f"http://example.org/locations/{location_id}")

    # Check if location exists
    if (location_uri, RDF.type, GEO.Location) not in graph:
        return None

    # Find property for this location
    property_uri = None
    for prop in graph.subjects(GEO.locationId, Literal(location_id)):
        if (prop, RDF.type, GEO.Property) in graph:
            property_uri = prop
            break

    if not property_uri:
        return None

    # Extract location data
    address = str(graph.value(location_uri, GEO.address))
    postal = str(graph.value(location_uri, GEO.postalCode))
    municipality = str(graph.value(location_uri, GEO.municipality))

    # Extract property data
    cadastral_id = str(graph.value(property_uri, GEO.cadastralId))
    owner = str(graph.value(property_uri, GEO.owner))
    surface = str(graph.value(property_uri, GEO.surfaceArea))
    land_use = str(graph.value(property_uri, GEO.landUse))
    building_type = str(graph.value(property_uri, GEO.buildingType))
    construction_year = str(graph.value(property_uri, GEO.constructionYear))

    return {
        "@context": {"geo": "http://example.org/geospatial#"},
        "@id": str(property_uri),
        "@type": "geo:Property",
        "geo:locationId": location_id,
        "geo:cadastralId": cadastral_id,
        "geo:address": address,
        "geo:postalCode": postal,
        "geo:municipality": municipality,
        "geo:owner": owner,
        "geo:surfaceArea": surface,
        "geo:landUse": land_use,
        "geo:buildingType": building_type,
        "geo:constructionYear": construction_year,
    }


def list_properties():
    """List all cadastral properties"""
    properties = []
    for property_uri in graph.subjects(RDF.type, GEO.Property):
        cadastral_id = str(graph.value(property_uri, GEO.cadastralId))
        loc_id = str(graph.value(property_uri, GEO.locationId))
        owner = str(graph.value(property_uri, GEO.owner))
        surface = str(graph.value(property_uri, GEO.surfaceArea))

        # Get address from location
        location_uri = URIRef(f"http://example.org/locations/{loc_id}")
        address = str(graph.value(location_uri, GEO.address))

        properties.append(
            {
                "@id": str(property_uri),
                "@type": "geo:Property",
                "geo:cadastralId": cadastral_id,
                "geo:locationId": loc_id,
                "geo:address": address,
                "geo:owner": owner,
                "geo:surfaceArea": surface,
            }
        )

    return {"@context": {"geo": "http://example.org/geospatial#"}, "@graph": properties}


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
                "serverInfo": {"name": "kadaster-service", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "get_property",
                        "description": (
                            "Get cadastral property data by location ID. "
                            "Returns Kadaster registry data in JSON-LD format."
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
                        "name": "list_properties",
                        "description": (
                            "List all cadastral properties. Returns RDF data in JSON-LD format."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "get_property":
            location_id = tool_args.get("location_id")
            result = get_property(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Property for location {location_id} not found",
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

        elif tool_name == "list_properties":
            result = list_properties()
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
