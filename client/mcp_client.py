"""
MCP Client Module
Handles MCP (Model Context Protocol) interactions with Docker containers
"""

import json
import logging

logger = logging.getLogger(__name__)


def read_docker_stream(socket, _stream_type_filter=None):
    """
    Read from Docker multiplexed stream

    Args:
        socket: Docker socket
        _stream_type_filter: If specified, only return data from this stream (1=stdout, 2=stderr)
                            (Currently unused but kept for API compatibility)

    Returns:
        Decoded string data from the specified stream type
    """
    result = b""
    stderr_logs = []

    while True:
        # Read Docker multiplexing header (8 bytes)
        header = socket._sock.recv(8)
        if len(header) < 8:
            break

        stream_type = header[0]
        # Size is in bytes 4-8 (big-endian uint32)
        size = int.from_bytes(header[4:8], byteorder="big")

        # Read the payload
        payload = b""
        while len(payload) < size:
            chunk = socket._sock.recv(size - len(payload))
            if not chunk:
                break
            payload += chunk

        if stream_type == 0x02:  # stderr
            # Log stderr messages
            try:
                stderr_msg = payload.decode("utf-8", errors="replace").strip()
                if stderr_msg:
                    stderr_logs.append(stderr_msg)
                    logger.info(f"[Agent stderr] {stderr_msg}")
            except Exception as e:
                logger.warning(f"Error decoding stderr: {e}")
        elif stream_type == 0x01:  # stdout
            result += payload
            # Check if we have a complete JSON-RPC message (ends with newline)
            if payload.endswith(b"\n"):
                break

    # Log any collected stderr at the end
    if stderr_logs:
        logger.debug(f"Collected {len(stderr_logs)} stderr messages from agent")

    return result.decode("utf-8", errors="replace").strip()


def list_mcp_tools(docker_client, container_name):
    """
    List available MCP tools from a running container

    Args:
        docker_client: Docker client instance
        container_name: Name of the container to query

    Returns:
        List of tool definitions or empty list if unavailable
    """
    try:
        container = docker_client.containers.get(container_name)
        if container.status != "running":
            return []

        # Initialize MCP connection
        init_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "eai-orchestrator", "version": "1.0.0"},
                    },
                }
            )
            + "\n"
        )

        exec_result = container.exec_run(
            "python -u server.py",
            stdin=True,
            stdout=True,
            stderr=True,
            detach=False,
            tty=False,
            socket=True,
        )

        socket = exec_result.output
        socket._sock.sendall(init_request.encode())

        # Read initialization response
        read_docker_stream(socket)

        # List tools
        list_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                }
            )
            + "\n"
        )

        socket._sock.sendall(list_request.encode())

        # Read tools response
        decoded_response = read_docker_stream(socket)
        socket._sock.close()

        try:
            result = json.loads(decoded_response)
            return result.get("result", {}).get("tools", [])
        except json.JSONDecodeError:
            return []

    except Exception as e:
        logger.debug(f"Error listing tools for {container_name}: {e}")
        return []


def call_mcp_tool(docker_client, container_name, tool_name, arguments=None):
    """
    Call an MCP tool in a running container

    Args:
        docker_client: Docker client instance
        container_name: Name of the container to call the tool in
        tool_name: Name of the MCP tool to call
        arguments: Optional dictionary of arguments to pass to the tool

    Returns:
        Dictionary containing the tool result or error
    """
    if arguments is None:
        arguments = {}
    try:
        container = docker_client.containers.get(container_name)
        if container.status != "running":
            return {"error": f"Container {container_name} is not running"}

        # Initialize MCP connection
        init_request = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "eai-orchestrator", "version": "1.0.0"},
                    },
                }
            )
            + "\n"
        )

        exec_result = container.exec_run(
            "python -u server.py",
            stdin=True,
            stdout=True,
            stderr=True,  # Capture stderr for logging
            detach=False,
            tty=False,
            socket=True,
        )

        socket = exec_result.output
        socket._sock.sendall(init_request.encode())

        # Read initialization response
        init_response = read_docker_stream(socket)
        logger.info(f"Init response: {init_response[:200]}")

        # Call the tool
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

        socket._sock.sendall(tool_request.encode())

        # Read tool response
        decoded_response = read_docker_stream(socket)
        socket._sock.close()

        logger.info(f"Tool response (first 200 chars): {decoded_response[:200]}")

        try:
            result = json.loads(decoded_response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response text: {decoded_response}")
            return {"error": f"Invalid JSON response: {str(e)}"}

        return result

    except Exception as e:
        import traceback

        logger.error(f"Error in call_mcp_tool: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}
