# MCP Agent Architecture (Option 2)

## Architecture Overview

This system implements **Option 2: MCP Agent Server** - a pure MCP approach where the AI Agent is itself an MCP server that acts as a client to other MCP servers.

```
┌──────────────────────────────────────────────────────────┐
│                    User / Dashboard                       │
└─────────────────────────┬────────────────────────────────┘
                          │ MCP Protocol
                          ↓
                ┌──────────────────┐
                │  Agent Service   │  ← MCP Server (exposes ask_question)
                │  (Meta-Agent)    │  ← MCP Client (queries others)
                └────────┬─────────┘
                         │ MCP Protocol
        ┌────────────────┼────────────────┐
        ↓                ↓                 ↓
   ┌─────────┐      ┌─────────┐     ┌──────────────┐
   │Kadaster │      │   CBS   │     │Rijkswaterstaat│
   │  (MCP)  │      │  (MCP)  │     │     (MCP)     │
   └─────────┘      └─────────┘     └──────────────┘
```

## Why This Architecture?

### **Protocol Consistency**
Everything speaks MCP - no mixing of protocols:
- Dashboard → Orchestrator → MCP services (including Agent)
- Agent → Other MCP services

### **Composability**
The agent is just another service that can be:
- Started/stopped like other services
- Queried via standard MCP tools
- Replaced or upgraded independently
- Used by any MCP client

### **Clean Separation**
- Data services (Kadaster, CBS, Rijkswaterstaat) → Pure data providers
- Agent service → Pure intelligent orchestrator
- No special case logic in the orchestrator

### **Scalability**
- Each service can be scaled independently
- Agent can be containerized and deployed anywhere
- Multiple agents can coexist

## Component Details

### 1. Agent MCP Server (`mcp-servers/agent-service/server.py`)

**Role:** Meta-Agent - both MCP server and MCP client

**Exposes (as MCP Server):**
```json
{
  "tool": "ask_question",
  "description": "Ask a natural language question about Dutch locations",
  "arguments": {
    "question": "Your question here"
  }
}
```

**Consumes (as MCP Client):**
- Kadaster service tools: `get_property`, `list_properties`
- CBS service tools: `get_statistics`, `list_locations`, `get_demographics`
- Rijkswaterstaat tools: `get_infrastructure`, `list_roads`, `get_water_level`

**Internal Architecture:**
```python
1. Receive ask_question tool call via MCP
2. Use Azure OpenAI to analyze the question
3. AI model decides which backend services to query
4. Execute MCP tool calls to backend services (via docker exec stdio)
5. AI model synthesizes results from all sources
6. Return synthesized answer via MCP response
```

### 2. Backend MCP Services

**Kadaster, CBS, Rijkswaterstaat** remain unchanged:
- Pure data providers
- No knowledge of the agent
- Standard MCP stdio transport
- RDF/JSON-LD responses

### 3. Orchestrator

**Minimal changes:**
- Added agent-service to SERVICES dictionary
- No special agent endpoints
- Treats agent like any other MCP service

### 4. Dashboard

**Unified interface:**
- Agent appears as a service box (with 🤖 icon)
- Select "AI Agent" from dropdown
- Call `ask_question` tool with question JSON
- Results displayed like any other tool

## Technical Implementation

### Agent Service Communication

The agent uses **stdio transport** to communicate with backend services:

```python
def call_mcp_service(service_name, tool_name, arguments):
    # Start MCP server in docker container
    process = subprocess.Popen(
        ['docker', 'exec', '-i', service_name, 'python', '-u', 'server.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True
    )

    # Send initialize request
    init_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        ...
    }

    # Send tool call request
    tool_request = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments}
    }

    # Read response
    response = process.stdout.readline()
    return json.loads(response)
```

### Agent Logic Flow

```
User Question: "What is the population of Amsterdam?"
    ↓
Agent MCP Server receives: ask_question(question="...")
    ↓
Azure OpenAI analyzes question
    ↓
AI model decides: "Need CBS demographic data for Amsterdam"
    ↓
Agent calls: call_mcp_service("eai-cbs-service", "get_statistics", {location_id: "LOC001"})
    ↓
CBS returns population data
    ↓
AI model synthesizes: "Amsterdam has a population of 872,680..."
    ↓
Agent returns answer via MCP response
```

### Multi-Source Query Example

```
Question: "Compare Amsterdam and Rotterdam"
    ↓
AI model decides: Need data from multiple services and locations
    ↓
Tool calls (parallel):
  - Kadaster: get_property(LOC001)
  - Kadaster: get_property(LOC003)
  - CBS: get_statistics(LOC001)
  - CBS: get_statistics(LOC003)
  - Rijkswaterstaat: get_infrastructure(LOC001)
  - Rijkswaterstaat: get_infrastructure(LOC003)
    ↓
AI model synthesizes comprehensive comparison
    ↓
Returns detailed answer
```

## Setup & Deployment

### 1. Build the Agent Service

The agent service requires:
- Python 3.11+
- openai package (Azure OpenAI SDK)
- Docker socket access (to call other containers)
- Azure OpenAI environment variables (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, etc.)

**Dockerfile:**
```dockerfile
FROM python:3.14-slim
RUN pip install openai rdflib
COPY server.py .
CMD ["python", "-u", "server.py"]
```

### 2. Docker Compose Configuration

```yaml
agent-service:
  build: ./mcp-servers/agent-service
  container_name: eai-agent-service
  env_file:
    - ../.env
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  depends_on:
    - kadaster-service
    - cbs-service
    - rijkswaterstaat-service
```

**Key points:**
- Azure OpenAI credentials loaded from `.env` file
- Docker socket mounted to allow calling other containers
- Depends on data services

### 3. Start All Services

```bash
# Configure .env file with Azure OpenAI credentials
# (See project root .env file)

# Start orchestrator (builds all images)
cd client
python orchestrator.py

# Or use docker-compose
docker-compose up --build
```

### 4. Query the Agent

**Via Dashboard:**
1. Start all services including "AI Agent"
2. Select "AI Agent" from service dropdown
3. Select `ask_question` tool
4. Enter: `{"question": "What is the population of Utrecht?"}`
5. Execute query

**Via Direct MCP Call:**
```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {...}}' | \
  docker exec -i eai-agent-service python -u server.py

echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "ask_question", "arguments": {"question": "What is the population of Amsterdam?"}}}' | \
  docker exec -i eai-agent-service python -u server.py
```

## Advantages Over Option 1 (REST Endpoint)

| Aspect | Option 1 (REST) | Option 2 (MCP) |
|--------|----------------|----------------|
| Protocol | Mixed (MCP + REST) | Pure MCP |
| Integration | Special case in orchestrator | Standard service |
| Scalability | Tied to orchestrator | Independent |
| Composability | Single use | Reusable by any MCP client |
| Architecture | Layered violation | Clean separation |
| Testability | Harder to test | Easy to test as MCP server |

## Comparison to Option 3 (Standalone Script)

Option 3 would be a Python script that directly connects to services. This is simpler but:
- Not integrated with the dashboard
- Not manageable like other services
- Can't be queried via MCP protocol
- Less reusable

Option 2 combines the benefits of all approaches:
- Integrated with dashboard ✅
- Manageable as a service ✅
- Speaks MCP protocol ✅
- Highly reusable ✅

## Future Enhancements

### 1. Agent Capabilities

**Streaming responses:**
```python
# Return partial results as they're generated
for chunk in claude_stream:
    yield {"type": "progress", "text": chunk}
```

**Multi-turn conversations:**
```python
# Maintain conversation state
{
  "tool": "ask_followup",
  "arguments": {
    "question": "What about Utrecht?",
    "conversation_id": "conv-123"
  }
}
```

### 2. Multiple Agents

Deploy specialized agents:
```
agent-demographic: Expert in CBS data
agent-property: Expert in Kadaster data
agent-infrastructure: Expert in Rijkswaterstaat data
agent-general: Queries all sources
```

### 3. Agent Chaining

Agents can call other agents:
```
User → General Agent → Demographic Agent → CBS Service
                     → Property Agent → Kadaster Service
```

### 4. Real Data Integration

Connect to actual APIs:
```python
# In agent-service
def call_real_kadaster_api():
    response = requests.get("https://api.kadaster.nl/...")
    return process_real_data(response)
```

## Troubleshooting

### Agent service won't start

**Issue:** Container fails to start or immediately exits

**Check:**
```bash
docker logs eai-agent-service
```

**Common causes:**
- Azure OpenAI credentials not configured in `.env`
- Python dependencies missing
- Syntax error in server.py

### Agent returns errors

**Issue:** Agent tool call fails

**Check logs:**
```bash
docker logs eai-agent-service 2>&1 | grep -i error
```

**Common causes:**
- Backend services not running
- Docker socket not mounted
- Invalid question format

### Slow responses

**Issue:** Agent takes long time to respond

**Normal behavior:**
- 3-5 seconds for simple queries
- 8-15 seconds for complex multi-source queries

**To investigate:**
```bash
# Watch agent logs in real-time
docker logs -f eai-agent-service
```

Look for which services are being called and how long each takes.

## Security Considerations

### API Key Management

**Never commit credentials:**
```bash
# .gitignore
.env
**/.env*
```

**Use environment variables from .env file:**
```bash
# .env file
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key-here
```

**Or use secrets management:**
```bash
docker secret create azure_openai_key ./api_key.txt
```

### Docker Socket Access

The agent needs Docker socket access to call other containers. This is powerful and should be protected:

**Production considerations:**
- Run in isolated network
- Use Docker API with authentication
- Limit container permissions

### Input Validation

The agent validates questions but malicious inputs could:
- Cause expensive API calls
- Trigger unintended service queries

**Mitigations:**
- Rate limiting
- Input sanitization
- Max token limits in Claude calls

## Performance Optimization

### Caching

Cache frequent questions:
```python
@lru_cache(maxsize=100)
def get_cached_answer(question):
    return ask_question(question)
```

### Parallel Tool Calls

The AI model can execute multiple tools in parallel:
```python
# AI model decides to call 3 services at once
with ThreadPoolExecutor() as executor:
    futures = [
        executor.submit(call_service, "kadaster", ...),
        executor.submit(call_service, "cbs", ...),
        executor.submit(call_service, "rijkswaterstaat", ...)
    ]
    results = [f.result() for f in futures]
```

### Connection Pooling

Reuse connections to backend services:
```python
# Keep subprocess alive for multiple queries
class PersistentMCPClient:
    def __init__(self, service_name):
        self.process = subprocess.Popen(...)

    def call_tool(self, name, args):
        # Reuse existing process
        ...
```

## Conclusion

**Option 2 (MCP Agent Server)** provides the cleanest, most scalable architecture for an AI agent in an MCP-based system:

✅ Pure MCP protocol throughout
✅ Agent is a first-class service
✅ Easy to test, deploy, and scale
✅ Composable and reusable
✅ Clean architectural separation

This approach demonstrates best practices for building intelligent agents in distributed systems.

---

**Architecture Type:** Meta-Agent Pattern
**Protocol:** Model Context Protocol (MCP)
**Agent Model:** Azure OpenAI (GPT-4o or GPT-4o-mini)
**Transport:** stdio (JSON-RPC 2.0)
