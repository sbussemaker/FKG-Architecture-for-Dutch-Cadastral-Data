#!/usr/bin/env python3
"""
BAG Service MCP Server
======================

Data Source: Basisregistratie Adressen en Gebouwen (BAG - kadaster.nl/bag)

Purpose:
    Provides official Dutch address and building data including street addresses,
    postal codes, building purposes, construction years, surface areas, and
    building status information.

Ontology (RDF Namespace: http://imx-geo-prime.org/geospatial#):
    - geo:Address: Address registration
        - geo:locationId: Unique identifier linking to other registers
        - geo:streetName: Street name
        - geo:houseNumber: House number
        - geo:postalCode: Dutch postal code (e.g., "1012 LG")
        - geo:municipality: Municipality/city name
        - geo:province: Province name

    - geo:Building: Building registration
        - geo:locationId: Links to corresponding Address
        - geo:buildingId: BAG building identifier
        - geo:buildingPurpose: Primary use (residential/office/retail/industrial/etc.)
        - geo:constructionYear: Year of construction (xsd:integer)
        - geo:buildingStatus: Current status (in_use/under_construction/demolished)
        - geo:surfaceArea: Gross floor area in m² (xsd:decimal)
        - geo:numberOfUnits: Number of addressable units (xsd:integer)

Tool Discovery Pattern:
    1. Use find_address(query) to search by street, city, or postal code
    2. Get locationId from results
    3. Use get_building(location_id) for building details

Cross-Service Linking:
    The geo:locationId is consistent across all MCP services (BAG, BGT, BRT, CBS,
    Rijkswaterstaat), allowing data from different sources to be combined.

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
    """Initialize BAG sample data for addresses and buildings"""

    addresses = [
        # (locationId, streetName, houseNumber, postalCode, municipality, province)
        ("LOC001", "Damrak", "1", "1012 LG", "Amsterdam", "Noord-Holland"),
        ("LOC002", "Oudegracht", "231", "3511 NK", "Utrecht", "Utrecht"),
        ("LOC003", "Coolsingel", "40", "3011 AD", "Rotterdam", "Zuid-Holland"),
        ("LOC004", "Grote Markt", "1", "9712 HN", "Groningen", "Groningen"),
        ("LOC005", "Markt", "87", "5611 EB", "Eindhoven", "Noord-Brabant"),
    ]

    buildings = [
        # (locationId, buildingId, purpose, constructionYear, status, surfaceArea, units)
        ("LOC001", "BAG-0363010012345678", "office", 1920, "in_use", 4500.0, 12),
        ("LOC002", "BAG-0344010023456789", "education", 1636, "in_use", 3200.0, 8),
        ("LOC003", "BAG-0599010034567890", "government", 1914, "in_use", 12000.0, 1),
        ("LOC004", "BAG-0014010045678901", "retail", 1890, "in_use", 850.0, 3),
        ("LOC005", "BAG-0772010056789012", "residential", 1965, "in_use", 120.0, 1),
    ]

    for loc_id, street, house_num, postal, municipality, province in addresses:
        address_uri = URIRef(f"http://imx-geo-prime.org/bag/addresses/{loc_id}")

        graph.add((address_uri, RDF.type, GEO.Address))
        graph.add((address_uri, GEO.locationId, Literal(loc_id)))
        graph.add((address_uri, GEO.streetName, Literal(street)))
        graph.add((address_uri, GEO.houseNumber, Literal(house_num)))
        graph.add((address_uri, GEO.postalCode, Literal(postal)))
        graph.add((address_uri, GEO.municipality, Literal(municipality)))
        graph.add((address_uri, GEO.province, Literal(province)))

    for loc_id, building_id, purpose, year, status, area, units in buildings:
        building_uri = URIRef(f"http://imx-geo-prime.org/bag/buildings/{building_id}")

        graph.add((building_uri, RDF.type, GEO.Building))
        graph.add((building_uri, GEO.locationId, Literal(loc_id)))
        graph.add((building_uri, GEO.buildingId, Literal(building_id)))
        graph.add((building_uri, GEO.buildingPurpose, Literal(purpose)))
        graph.add((building_uri, GEO.constructionYear, Literal(year, datatype=XSD.integer)))
        graph.add((building_uri, GEO.buildingStatus, Literal(status)))
        graph.add((building_uri, GEO.surfaceArea, Literal(area, datatype=XSD.decimal)))
        graph.add((building_uri, GEO.numberOfUnits, Literal(units, datatype=XSD.integer)))


init_data()


def find_address(query):
    """Find addresses by searching street name, municipality, or postal code"""
    query_lower = query.lower()
    results = []

    for address_uri in graph.subjects(RDF.type, GEO.Address):
        loc_id = str(graph.value(address_uri, GEO.locationId))
        street = str(graph.value(address_uri, GEO.streetName))
        house_num = str(graph.value(address_uri, GEO.houseNumber))
        postal = str(graph.value(address_uri, GEO.postalCode))
        municipality = str(graph.value(address_uri, GEO.municipality))
        province = str(graph.value(address_uri, GEO.province))

        # Search in street, municipality, postal code, and location ID
        if (
            query_lower in street.lower()
            or query_lower in municipality.lower()
            or query_lower in postal.lower()
            or query_lower in loc_id.lower()
        ):
            results.append(
                {
                    "@type": "geo:Address",
                    "geo:locationId": loc_id,
                    "geo:streetName": street,
                    "geo:houseNumber": house_num,
                    "geo:postalCode": postal,
                    "geo:municipality": municipality,
                    "geo:province": province,
                }
            )

    return {"@context": {"geo": "http://imx-geo-prime.org/geospatial#"}, "@graph": results}


def get_building(location_id):
    """Get building data by location ID"""
    # Find building for this location
    building_uri = None
    for building in graph.subjects(RDF.type, GEO.Building):
        if str(graph.value(building, GEO.locationId)) == location_id:
            building_uri = building
            break

    if not building_uri:
        return None

    # Get address info
    address_uri = None
    for addr in graph.subjects(RDF.type, GEO.Address):
        if str(graph.value(addr, GEO.locationId)) == location_id:
            address_uri = addr
            break

    result = {
        "@context": {"geo": "http://imx-geo-prime.org/geospatial#"},
        "@id": str(building_uri),
        "@type": "geo:Building",
        "geo:locationId": location_id,
        "geo:buildingId": str(graph.value(building_uri, GEO.buildingId)),
        "geo:buildingPurpose": str(graph.value(building_uri, GEO.buildingPurpose)),
        "geo:constructionYear": str(graph.value(building_uri, GEO.constructionYear)),
        "geo:buildingStatus": str(graph.value(building_uri, GEO.buildingStatus)),
        "geo:surfaceArea": str(graph.value(building_uri, GEO.surfaceArea)),
        "geo:numberOfUnits": str(graph.value(building_uri, GEO.numberOfUnits)),
    }

    if address_uri:
        result["geo:address"] = {
            "geo:streetName": str(graph.value(address_uri, GEO.streetName)),
            "geo:houseNumber": str(graph.value(address_uri, GEO.houseNumber)),
            "geo:postalCode": str(graph.value(address_uri, GEO.postalCode)),
            "geo:municipality": str(graph.value(address_uri, GEO.municipality)),
        }

    return result


def list_addresses():
    """List all registered addresses"""
    addresses = []

    for address_uri in graph.subjects(RDF.type, GEO.Address):
        loc_id = str(graph.value(address_uri, GEO.locationId))
        street = str(graph.value(address_uri, GEO.streetName))
        house_num = str(graph.value(address_uri, GEO.houseNumber))
        municipality = str(graph.value(address_uri, GEO.municipality))

        addresses.append(
            {
                "@type": "geo:Address",
                "geo:locationId": loc_id,
                "geo:streetName": street,
                "geo:houseNumber": house_num,
                "geo:municipality": municipality,
            }
        )

    return {"@context": {"geo": "http://imx-geo-prime.org/geospatial#"}, "@graph": addresses}


def get_address(location_id):
    """Get full address details by location ID"""
    address_uri = None
    for addr in graph.subjects(RDF.type, GEO.Address):
        if str(graph.value(addr, GEO.locationId)) == location_id:
            address_uri = addr
            break

    if not address_uri:
        return None

    return {
        "@context": {"geo": "http://imx-geo-prime.org/geospatial#"},
        "@id": str(address_uri),
        "@type": "geo:Address",
        "geo:locationId": location_id,
        "geo:streetName": str(graph.value(address_uri, GEO.streetName)),
        "geo:houseNumber": str(graph.value(address_uri, GEO.houseNumber)),
        "geo:postalCode": str(graph.value(address_uri, GEO.postalCode)),
        "geo:municipality": str(graph.value(address_uri, GEO.municipality)),
        "geo:province": str(graph.value(address_uri, GEO.province)),
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
                    "name": "bag-service",
                    "version": "1.0.0",
                    "description": (
                        "BAG (Basisregistratie Adressen en Gebouwen) MCP Server. "
                        "Provides official Dutch address and building registration data. "
                        "Data source: Kadaster BAG (kadaster.nl/bag). "
                        "Use this service for questions about: street addresses, postal codes, "
                        "building purposes (residential/office/retail), construction years, "
                        "building status, and floor areas."
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
                        "name": "find_address",
                        "description": (
                            "Search for addresses in the BAG register by street name, city, "
                            "or postal code. USE THIS TOOL FIRST when you need to find a "
                            "location. Returns location IDs that can be used with get_building "
                            "and other BAG tools, as well as with BGT and BRT services. "
                            "EXAMPLE: find_address('Amsterdam') returns all Amsterdam addresses. "
                            "EXAMPLE: find_address('Damrak') returns addresses on Damrak street."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": (
                                        "Search term: street name, city/municipality, or postal "
                                        "code. Case-insensitive partial matching supported."
                                    ),
                                }
                            },
                            "required": ["query"],
                        },
                    },
                    {
                        "name": "get_building",
                        "description": (
                            "Get detailed building information from BAG for a specific location. "
                            "PREREQUISITE: Use find_address first to get a valid locationId. "
                            "RETURNS: Building purpose (residential/office/retail/education/etc.), "
                            "construction year, building status, surface area in m², number of "
                            "units, and the linked address. "
                            "USE FOR: Questions about what type of building is at a location, "
                            "when it was built, or how large it is."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": (
                                        "Location identifier from find_address. "
                                        "Format: 'LOC' followed by digits (e.g., 'LOC001')."
                                    ),
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                    {
                        "name": "get_address",
                        "description": (
                            "Get full address details for a location ID. "
                            "RETURNS: Street name, house number, postal code, municipality, "
                            "and province. Use when you need complete address information."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "location_id": {
                                    "type": "string",
                                    "description": "Location identifier from find_address.",
                                }
                            },
                            "required": ["location_id"],
                        },
                    },
                    {
                        "name": "list_addresses",
                        "description": (
                            "List ALL addresses in the BAG database. Use when you need an "
                            "overview of available locations or want to browse without a "
                            "specific search term. Returns summary info for each address."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "find_address":
            query = tool_args.get("query", "")
            result = find_address(query)

            if not result.get("@graph"):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"No addresses found matching '{query}'. "
                                    "Try searching by city name, street, or postal code."
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

        elif tool_name == "get_building":
            location_id = tool_args.get("location_id")
            result = get_building(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No building found for location {location_id}",
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

        elif tool_name == "get_address":
            location_id = tool_args.get("location_id")
            result = get_address(location_id)

            if result is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"No address found for location {location_id}",
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

        elif tool_name == "list_addresses":
            result = list_addresses()
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
