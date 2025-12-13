#!/usr/bin/env python3
"""
AI Agent MCP Server

This is a meta-MCP-server that acts as both an MCP server (exposing tools to clients)
and an MCP client (querying other MCP servers like Kadaster, CBS, Rijkswaterstaat).

It uses Azure OpenAI to understand natural language questions and intelligently query
the appropriate backend services.
"""

import json
import sys
import os
import subprocess
from typing import Dict, Any, List
from openai import AzureOpenAI

# Initialize Azure OpenAI client
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

if AZURE_ENDPOINT and AZURE_API_KEY and AZURE_DEPLOYMENT:
    client = AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION
    )
else:
    client = None
    print("Warning: Azure OpenAI credentials not set. Agent will return errors.", file=sys.stderr)
    print(f"Required: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME", file=sys.stderr)

# MCP service configuration
MCP_SERVICES = {
    "query_kadaster": {
        "container": "eai-kadaster-service",
        "description": "Query the Kadaster (Dutch Land Registry) for property ownership, cadastral data, building information. Use for questions about properties, owners, buildings, land use."
    },
    "query_cbs": {
        "container": "eai-cbs-service",
        "description": "Query CBS (Statistics Netherlands) for demographics, population, income, unemployment. Use for statistical questions."
    },
    "query_rijkswaterstaat": {
        "container": "eai-rijkswaterstaat-service",
        "description": "Query Rijkswaterstaat for infrastructure, roads, bridges, water bodies, water levels. Use for infrastructure questions."
    }
}

# Cache for dynamically discovered tools
_BACKEND_TOOLS_CACHE = None

def discover_tools_from_service(container_name: str) -> List[Dict[str, Any]]:
    """
    Discover available tools from an MCP service using tools/list

    Args:
        container_name: Name of the Docker container

    Returns:
        List of tool definitions
    """
    try:
        process = subprocess.Popen(
            ['docker', 'exec', '-i', container_name, 'python', '-u', 'server.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Send initialize request
        init_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-service", "version": "1.0.0"}
            }
        }) + "\n"

        process.stdin.write(init_request)
        process.stdin.flush()

        # Read initialize response
        init_response = process.stdout.readline()

        # Send tools/list request
        tools_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }) + "\n"

        process.stdin.write(tools_request)
        process.stdin.flush()

        # Read tools/list response
        tools_response = process.stdout.readline()

        # Close the process
        process.stdin.close()
        process.terminate()

        # Parse and return the tools
        response_data = json.loads(tools_response)
        tools = response_data.get("result", {}).get("tools", [])

        return tools

    except Exception as e:
        print(f"Error discovering tools from {container_name}: {e}", file=sys.stderr)
        return []

def get_backend_tools() -> List[Dict[str, Any]]:
    """
    Get backend tools, discovering them dynamically if not cached

    Returns:
        List of tool definitions for Claude
    """
    global _BACKEND_TOOLS_CACHE

    if _BACKEND_TOOLS_CACHE is not None:
        return _BACKEND_TOOLS_CACHE

    backend_tools = []

    for service_name, service_info in MCP_SERVICES.items():
        container = service_info["container"]
        service_desc = service_info["description"]

        # Discover tools from the service
        discovered_tools = discover_tools_from_service(container)

        if not discovered_tools:
            print(f"Warning: No tools discovered from {service_name}", file=sys.stderr)
            continue

        # Extract tool names for the enum
        tool_names = [tool["name"] for tool in discovered_tools]

        # Create a wrapper tool for this service
        wrapper_tool = {
            "name": service_name,
            "description": service_desc,
            "input_schema": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": tool_names,
                        "description": f"The {service_name} tool to call"
                    },
                    "location_id": {
                        "type": "string",
                        "description": "Location ID (LOC001=Amsterdam, LOC002=Utrecht, LOC003=Rotterdam). Required for most tools."
                    }
                },
                "required": ["tool"]
            }
        }

        backend_tools.append(wrapper_tool)
        print(f"[Agent] Discovered {len(tool_names)} tools from {service_name}: {tool_names}", file=sys.stderr)

    _BACKEND_TOOLS_CACHE = backend_tools
    return backend_tools

def call_mcp_service(service_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call another MCP service using stdio transport

    Args:
        service_name: Name of the Docker container (e.g., 'eai-kadaster-service')
        tool_name: Name of the tool to call
        arguments: Arguments for the tool

    Returns:
        The result from the MCP service
    """
    try:
        # Start the MCP server container and communicate via stdio
        process = subprocess.Popen(
            ['docker', 'exec', '-i', service_name, 'python', '-u', 'server.py'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Send initialize request
        init_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent-service", "version": "1.0.0"}
            }
        }) + "\n"

        process.stdin.write(init_request)
        process.stdin.flush()

        # Read initialize response
        init_response = process.stdout.readline()

        # Send tool call request
        tool_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }) + "\n"

        process.stdin.write(tool_request)
        process.stdin.flush()

        # Read tool response
        tool_response = process.stdout.readline()

        # Close the process
        process.stdin.close()
        process.terminate()

        # Parse and return the result
        response_data = json.loads(tool_response)
        return response_data.get("result", {})

    except Exception as e:
        return {"error": str(e)}

def convert_tools_to_openai_format(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert MCP tool definitions to OpenAI function calling format

    Args:
        tools: List of MCP tool definitions

    Returns:
        List of tools in OpenAI format
    """
    openai_tools = []
    for tool in tools:
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools

def execute_backend_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a backend MCP tool"""

    # Get container name from MCP_SERVICES configuration
    service_info = MCP_SERVICES.get(tool_name)
    if not service_info:
        return {"error": f"Unknown tool: {tool_name}"}

    container_name = service_info["container"]
    mcp_tool = tool_input["tool"]
    arguments = {"location_id": tool_input.get("location_id")} if "location_id" in tool_input else {}

    # Call the backend MCP service
    result = call_mcp_service(container_name, mcp_tool, arguments)

    return result

def ask_question(question: str) -> str:
    """
    Use Azure OpenAI to answer a question by querying backend MCP services

    Args:
        question: Natural language question about locations

    Returns:
        Natural language answer synthesized from multiple sources
    """
    if not client:
        return "Error: Azure OpenAI credentials not set. Cannot use AI agent."

    messages = [
        {
            "role": "system",
            "content": """You are an expert assistant with access to Dutch geospatial data from three government agencies:
- Kadaster (Land Registry): Property ownership, cadastral data, buildings
- CBS (Statistics Netherlands): Demographics, population, income statistics
- Rijkswaterstaat (Infrastructure & Water): Roads, bridges, canals, water levels

Available locations:
- LOC001: Amsterdam (Damrak 1)
- LOC002: Utrecht (Oudegracht 231)
- LOC003: Rotterdam (Coolsingel 40)

Use the available tools to gather information and provide a comprehensive answer."""
        },
        {
            "role": "user",
            "content": question
        }
    ]

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Get backend tools and convert to OpenAI format
        backend_tools = get_backend_tools()
        openai_tools = convert_tools_to_openai_format(backend_tools)

        # Call Azure OpenAI with tools
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            max_tokens=4096,
            tools=openai_tools,
            messages=messages
        )

        message = response.choices[0].message

        # Check if the model wants to use tools
        if message.tool_calls:
            # Add assistant's message to conversation
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            })

            # Execute each tool call
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_input = json.loads(tool_call.function.arguments)

                print(f"[Agent] Calling {tool_name}: {tool_input}", file=sys.stderr)

                # Execute the tool
                result = execute_backend_tool(tool_name, tool_input)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, indent=2)
                })

        elif message.content:
            # Model provided a final answer
            return message.content
        else:
            return "I couldn't generate a response."

    return "Maximum iterations reached without completing the query."

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
                    "name": "agent-service",
                    "version": "1.0.0",
                    "description": "AI Agent that queries Kadaster, CBS, and Rijkswaterstaat"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "ask_question",
                        "description": "Ask a natural language question about Dutch locations. The agent will intelligently query Kadaster, CBS, and Rijkswaterstaat services and synthesize a comprehensive answer.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "Your question about locations, demographics, properties, or infrastructure (e.g., 'What is the population of Amsterdam?')"
                                }
                            },
                            "required": ["question"]
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "ask_question":
            question = tool_args.get("question")

            if not question:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": "Error: Question is required"}],
                        "isError": True
                    }
                }

            print(f"[Agent] Received question: {question}", file=sys.stderr)

            try:
                answer = ask_question(question)

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": answer
                            }
                        ]
                    }
                }
            except Exception as e:
                import traceback
                traceback.print_exc(file=sys.stderr)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                        "isError": True
                    }
                }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}"
        }
    }

def main():
    """Main MCP server loop using stdio transport"""
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)

if __name__ == "__main__":
    main()
