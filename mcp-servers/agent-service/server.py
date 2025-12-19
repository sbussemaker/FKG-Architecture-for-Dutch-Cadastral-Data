#!/usr/bin/env python3
"""
AI Agent MCP Server

This is a meta-MCP-server that acts as both an MCP server (exposing tools to clients)
and an MCP client (querying other MCP servers like Kadaster, CBS, Rijkswaterstaat).

It uses Azure OpenAI to understand natural language questions and intelligently query
the appropriate backend services.
"""

import json
import logging
import os
import subprocess
import sys
from typing import Any, cast

from openai import AzureOpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallParam,
    ChatCompletionToolMessageParam,
    ChatCompletionToolParam,
)

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()
log_level = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] [Agent] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

logger.info(f"Started service with log level {log_level}")

# Initialize Azure OpenAI client
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

if AZURE_ENDPOINT and AZURE_API_KEY and AZURE_DEPLOYMENT:
    client = AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT, api_key=AZURE_API_KEY, api_version=AZURE_API_VERSION
    )
    logger.info(
        f"Azure OpenAI client initialized "
        f"(endpoint={AZURE_ENDPOINT}, deployment={AZURE_DEPLOYMENT})"
    )
else:
    client = None
    logger.warning("Azure OpenAI credentials not set. Agent will return errors.")
    logger.warning(
        "Required: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME"
    )

# MCP service configuration
MCP_SERVICES = {
    "Kadaster": {
        "container": "eai-kadaster-service",
        "description": (
            "Query the Kadaster (Dutch Land Registry) for property ownership, "
            "cadastral data, building information. Use for questions about "
            "properties, owners, buildings, land use."
        ),
    },
    "CBS": {
        "container": "eai-cbs-service",
        "description": (
            "Query CBS (Statistics Netherlands) for demographics, population, "
            "income, unemployment. Use for statistical questions."
        ),
    },
    "Rijkswaterstaat": {
        "container": "eai-rijkswaterstaat-service",
        "description": (
            "Query Rijkswaterstaat for infrastructure, roads, bridges, water "
            "bodies, water levels. Use for infrastructure questions."
        ),
    },
}

# Cache for dynamically discovered tools
# Structure: {
#   'Kadaster': {
#       'container': 'eai-kadaster-service',
#       'wrapper_tool': {...},
#       'discovered_tools': [...]
#   },
#   ...
# }
_BACKEND_TOOLS_CACHE: dict[str, dict[str, Any]] | None = None


def discover_tools_from_service(container_name: str) -> list[dict[str, Any]]:
    """
    Discover available tools from an MCP service using tools/list

    Args:
        container_name: Name of the Docker container

    Returns:
        List of tool definitions
    """
    try:
        process = subprocess.Popen(
            ["docker", "exec", "-i", container_name, "python", "-u", "server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Send initialize request
        init_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "agent-service", "version": "1.0.0"},
                    },
                }
            )
            + "\n"
        )

        if process.stdin is None or process.stdout is None:
            raise RuntimeError(f"Failed to create process stdin/stdout for {container_name}")

        process.stdin.write(init_request)
        process.stdin.flush()

        # Read initialize response
        _ = process.stdout.readline()

        # Send tools/list request
        tools_request = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n"

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
        logger.error(f"Error discovering tools from {container_name}: {e}")
        return []


def get_backend_tools() -> list[dict[str, Any]]:
    """
    Get backend tools, discovering them dynamically if not cached

    Returns:
        List of tool definitions for Claude
    """
    global _BACKEND_TOOLS_CACHE

    if _BACKEND_TOOLS_CACHE is not None:
        # Return just the wrapper tools for OpenAI
        return [
            cache_entry["wrapper_tool"]
            for cache_entry in _BACKEND_TOOLS_CACHE.values()
            if "wrapper_tool" in cache_entry
        ]

    backend_tools_cache = {}

    for service_name, service_info in MCP_SERVICES.items():
        container = service_info["container"]
        service_desc = service_info["description"]

        # Discover tools from the service
        discovered_tools = discover_tools_from_service(container)

        if not discovered_tools:
            logger.warning(f"No tools discovered from {service_name}")
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
                        "description": f"The {service_name} tool to call",
                    },
                    "location_id": {
                        "type": "string",
                        "description": (
                            "Location ID (LOC001=Amsterdam, LOC002=Utrecht, "
                            "LOC003=Rotterdam). Required for most tools."
                        ),
                    },
                },
                "required": ["tool"],
            },
        }

        # Cache the service information
        backend_tools_cache[service_name] = {
            "container": container,
            "wrapper_tool": wrapper_tool,
            "discovered_tools": discovered_tools,
        }

        logger.info(f"Discovered {len(tool_names)} tools from {service_name}: {tool_names}")

    _BACKEND_TOOLS_CACHE = backend_tools_cache
    return [cache_entry["wrapper_tool"] for cache_entry in backend_tools_cache.values()]


def call_mcp_service(
    service_name: str, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """
    Call another MCP service using stdio transport

    Args:
        service_name: Name of the Docker container (e.g., 'eai-kadaster-service')
        tool_name: Name of the tool to call
        arguments: Arguments for the tool

    Returns:
        The result from the MCP service
    """
    logger.debug(f"Calling MCP service {service_name}, tool={tool_name}, args={arguments}")
    try:
        # Start the MCP server container and communicate via stdio
        process = subprocess.Popen(
            ["docker", "exec", "-i", service_name, "python", "-u", "server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Send initialize request
        init_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "agent-service", "version": "1.0.0"},
                    },
                }
            )
            + "\n"
        )

        if process.stdin is None or process.stdout is None:
            raise RuntimeError(f"Failed to create process stdin/stdout for {service_name}")

        process.stdin.write(init_request)
        process.stdin.flush()

        # Read initialize response
        _ = process.stdout.readline()

        # Send tool call request
        tool_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                }
            )
            + "\n"
        )

        process.stdin.write(tool_request)
        process.stdin.flush()

        # Read tool response
        tool_response = process.stdout.readline()

        # Close the process
        process.stdin.close()
        process.terminate()

        # Parse and return the result
        response_data = json.loads(tool_response)
        result = response_data.get("result", {})
        logger.debug(f"MCP service {service_name} returned: {json.dumps(result, indent=2)[:500]}")
        return result

    except Exception as e:
        logger.error(f"Error calling MCP service {service_name}: {e}")
        return {"error": str(e)}


def convert_tools_to_openai_format(tools: list[dict[str, Any]]) -> list[ChatCompletionToolParam]:
    """
    Convert MCP tool definitions to OpenAI function calling format

    Args:
        tools: List of MCP tool definitions

    Returns:
        List of tools in OpenAI format
    """
    openai_tools: list[ChatCompletionToolParam] = []
    for tool in tools:
        openai_tool = cast(
            ChatCompletionToolParam,
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            },
        )
        openai_tools.append(openai_tool)
    return openai_tools


def execute_backend_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a backend MCP tool"""

    # Ensure cache is populated
    get_backend_tools()

    logger.debug(f"execute_backend_tool called with tool_name={tool_name}, tool_input={tool_input}")

    # Handle case where OpenAI might concatenate service.tool names
    if "." in tool_name and (_BACKEND_TOOLS_CACHE is None or tool_name not in _BACKEND_TOOLS_CACHE):
        # Split "Rijkswaterstaat.get_water_level" into service and tool
        service_name, mcp_tool = tool_name.split(".", 1)
        logger.info(
            f"Detected dotted tool name, splitting into service={service_name}, tool={mcp_tool}"
        )

        if _BACKEND_TOOLS_CACHE is None or service_name not in _BACKEND_TOOLS_CACHE:
            return {"error": f"Unknown service: {service_name}"}

        cache_entry = _BACKEND_TOOLS_CACHE[service_name]
        container_name = cache_entry["container"]
        arguments = (
            {"location_id": tool_input.get("location_id")} if "location_id" in tool_input else {}
        )

    else:
        # Standard wrapper tool format
        if _BACKEND_TOOLS_CACHE is None or tool_name not in _BACKEND_TOOLS_CACHE:
            return {"error": f"Unknown tool: {tool_name}"}

        cache_entry = _BACKEND_TOOLS_CACHE[tool_name]
        container_name = cache_entry["container"]

        if "tool" not in tool_input:
            return {"error": f"Missing 'tool' parameter in tool_input: {tool_input}"}

        mcp_tool = tool_input["tool"]
        arguments = (
            {"location_id": tool_input.get("location_id")} if "location_id" in tool_input else {}
        )

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

    if not AZURE_DEPLOYMENT:
        return "Error: Azure OpenAI deployment name not set. Cannot use AI agent."

    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": (
                "You are an expert assistant with access to Dutch geospatial data "
                "from three government agencies:\n"
                "- Kadaster (Land Registry): Property ownership, cadastral data, buildings\n"
                "- CBS (Statistics Netherlands): Demographics, population, income statistics\n"
                "- Rijkswaterstaat (Infrastructure & Water): Roads, bridges, canals, "
                "water levels\n\n"
                "Available locations:\n"
                "- LOC001: Amsterdam (Damrak 1)\n"
                "- LOC002: Utrecht (Oudegracht 231)\n"
                "- LOC003: Rotterdam (Coolsingel 40)\n\n"
                "CRITICAL RULES:\n"
                "1. You MUST use the available tools to gather all information\n"
                "2. You MUST NOT make guesses or use general knowledge to answer questions\n"
                "3. You MUST ONLY answer based on data returned from the tools\n"
                "4. If a tool call fails or returns an error, inform the user that the "
                "data is unavailable\n"
                "5. If you cannot get data from the tools, say so explicitly - do NOT "
                "provide approximations or guesses\n"
                '6. NEVER use phrases like "approximately", "based on latest data", '
                '"prior to", or "around" unless that data came from a tool\n'
                "7. If tools don't return data, respond with: "
                '"I was unable to retrieve that information from the available data sources."\n\n'
                "CITATION REQUIREMENTS:\n"
                "8. For EACH piece of information in your answer, you MUST cite the "
                "source tool that provided it\n"
                '9. Use this format: "- **Field Name**: Value '
                '(Source: ServiceName > tool_name)"\n'
                '10. Example: "- **Owner**: Gemeente Amsterdam '
                '(Source: Kadaster > get_property_details)"\n'
                "11. If multiple tools provided related information, cite all relevant sources\n\n"
                "Your answers must be based EXCLUSIVELY on tool results. No exceptions."
            ),
        },
        {"role": "user", "content": question},
    ]

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Agent iteration {iteration}/{max_iterations}")

        # Get backend tools and convert to OpenAI format
        backend_tools = get_backend_tools()
        openai_tools = convert_tools_to_openai_format(backend_tools)

        # Call Azure OpenAI with tools
        # Use "auto" to allow the model to decide when it has enough info to answer
        logger.debug(f"Calling Azure OpenAI with {len(openai_tools)} tools available")
        response = client.chat.completions.create(
            model=AZURE_DEPLOYMENT,
            max_tokens=4096,
            tool_choice="auto",
            tools=openai_tools,
            messages=messages,
        )

        message = response.choices[0].message

        # Check if the model wants to use tools
        if message.tool_calls:
            logger.info(f"AI model wants to call {len(message.tool_calls)} tool(s)")

            # Add assistant's message to conversation
            tool_calls_param: list[ChatCompletionMessageToolCallParam] = []
            for tc in message.tool_calls:
                # Only handle function tool calls
                if tc.type == "function" and hasattr(tc, "function"):
                    tool_calls_param.append(
                        cast(
                            ChatCompletionMessageToolCallParam,
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            },
                        )
                    )

            assistant_message: ChatCompletionAssistantMessageParam = {
                "role": "assistant",
                "tool_calls": tool_calls_param,
            }
            messages.append(assistant_message)

            # Execute each tool call
            for tool_call in message.tool_calls:
                if tool_call.type == "function" and hasattr(tool_call, "function"):
                    tool_name = tool_call.function.name
                    tool_input = json.loads(tool_call.function.arguments)
                else:
                    continue

                logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

                # Execute the tool
                result = execute_backend_tool(tool_name, tool_input)

                # Log the result
                if "error" in result:
                    logger.error(f"Tool {tool_name} returned error: {result['error']}")
                else:
                    logger.info(f"Tool {tool_name} completed successfully")

                # Add tool result to messages
                tool_message: ChatCompletionToolMessageParam = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, indent=2),
                }
                messages.append(tool_message)

        elif message.content:
            # Model provided a final answer
            logger.info(f"AI model provided final answer (length: {len(message.content)} chars)")
            logger.debug(f"Final answer: {message.content[:200]}...")
            return message.content
        else:
            logger.warning("AI model returned no content and no tool calls")
            return "I couldn't generate a response."

    logger.warning(f"Maximum iterations ({max_iterations}) reached without completing the query")
    return "Maximum iterations reached without completing the query."


def handle_request(request):
    """Handle MCP JSON-RPC request"""
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    logger.info(f"hande {method} request")

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
                    "description": "AI Agent that queries Kadaster, CBS, and Rijkswaterstaat",
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
                        "name": "ask_question",
                        "description": (
                            "Ask a natural language question about Dutch locations. "
                            "The agent will intelligently query Kadaster, CBS, and "
                            "Rijkswaterstaat services and synthesize a comprehensive answer."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": (
                                        "Your question about locations, demographics, "
                                        "properties, or infrastructure "
                                        "(e.g., 'What is the population of Amsterdam?')"
                                    ),
                                }
                            },
                            "required": ["question"],
                        },
                    }
                ]
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "ask_question":
            question = tool_args.get("question")

            if not question:
                logger.error("ask_question called without a question parameter")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": "Error: Question is required"}],
                        "isError": True,
                    },
                }

            logger.info(f"Received question: {question}")

            try:
                answer = ask_question(question)
                logger.info("Successfully answered question")

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": answer}]},
                }
            except Exception as e:
                logger.exception(f"Error processing question: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                        "isError": True,
                    },
                }

    # Unknown method
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    """Main MCP server loop using stdio transport"""
    logger.info("Agent MCP server starting...")
    logger.info(f"Azure OpenAI configured: {client is not None}")

    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            logger.exception(f"Error handling request: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
