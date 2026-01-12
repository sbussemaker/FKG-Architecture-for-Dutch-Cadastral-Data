# AI Agent for Dutch Geospatial Data Integration

An intelligent agent powered by Azure OpenAI that can answer natural language questions about locations by querying multiple MCP services.

## Overview

The AI Agent acts as an **orchestrating LLM** that:
1. Understands your natural language question
2. Determines which MCP services need to be queried
3. Executes the necessary tool calls in parallel
4. Synthesizes information from multiple sources
5. Provides a comprehensive, natural language answer

```
┌─────────────────────────────────────────────────────────┐
│                      User Question                      │
│  "What is the population and infrastructure in Utrecht?"│
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
         ┌───────────────────────────────┐
         │   AI Agent (Azure OpenAI)     │
         │  - Parse question             │
         │  - Plan tool calls            │
         │  - Synthesize results         │
         └───────────────┬───────────────┘
                         │
        ┌────────────────┼────────────────┐
        ↓                ↓                 ↓
   ┌─────────┐     ┌─────────┐     ┌──────────────┐
   │Kadaster │     │   CBS   │     │Rijkswaterstaat│
   │Property │     │ Stats   │     │Infrastructure│
   └─────────┘     └─────────┘     └──────────────┘
                         │
                         ↓
              Comprehensive Answer
```

---

## Quick Start

### 1. Install Dependencies

```bash
cd /home/stefan/ais
uv sync  # Installs Azure OpenAI SDK
```

### 2. Configure Azure OpenAI

Create or edit the `.env` file at the project root:

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

### 3. Start the System

```bash
# Start orchestrator (builds all images including agent)
cd client
python orchestrator.py

# Open dashboard
open ../dashboard/index.html
```

### 4. Start Services

From the dashboard:
1. Start Kadaster, CBS, and Rijkswaterstaat services
2. Start the AI Agent service
3. Use the "🤖 AI Agent" panel to ask questions

---

## Usage

### Via Dashboard

1. Open the dashboard in your browser
2. Locate the "🤖 AI Agent (Ask Questions)" panel at the top
3. Type your question in the text area
4. Click "Ask AI Agent"
5. Watch as the agent queries services and synthesizes an answer

### Example Questions

**Simple queries:**
- "What is the population of Amsterdam?"
- "Who owns the property at Damrak 1?"
- "What is the water level in Utrecht?"

**Multi-source queries:**
- "Compare the population and average income between Amsterdam and Rotterdam"
- "What infrastructure exists near the Erasmusbrug in Rotterdam?"
- "Tell me about the property, demographics, and nearby infrastructure for Utrecht location LOC002"

**Complex analytical questions:**
- "Which city has the highest population density and what infrastructure supports it?"
- "What is the relationship between property age and population in these cities?"

### Via API

```bash
curl -X POST http://localhost:5000/api/agent/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the population of Utrecht?"}'
```

Response:
```json
{
  "question": "What is the population of Utrecht?",
  "answer": "According to CBS (Statistics Netherlands), Utrecht has a population of 361,966 people..."
}
```

---

## How It Works

### 1. Question Understanding

The AI model analyzes your question to understand:
- What information is being requested
- Which location(s) are mentioned
- Which agencies would have relevant data

### 2. Tool Selection

The agent chooses appropriate tools based on the question type:

| Question Type | Tools Used |
|--------------|------------|
| Population, demographics | `query_cbs` |
| Property ownership, buildings | `query_kadaster` |
| Roads, water, infrastructure | `query_rijkswaterstaat` |
| Comprehensive location info | All three tools |

### 3. Parallel Execution

If multiple tools are needed, the agent can execute them in parallel for faster responses.

### 4. Result Synthesis

The AI model combines data from all sources into a coherent, natural language answer, highlighting:
- Key facts from each source
- Relationships between data points
- Context and interpretation

### Agent Loop

The agent follows a loop pattern:

```python
1. User asks question
2. AI model decides which tools to use
3. Tools are executed → MCP services queried
4. Results returned to AI model
5. AI model synthesizes answer
   ├─ If more info needed: go to step 2
   └─ If complete: return answer to user
```

Maximum iterations: 5 (configurable)

---

## Architecture

### Design Pattern: MCP Agent Server

This system implements an **MCP Agent Server** - a pure MCP approach where the AI Agent is itself an MCP server that acts as a client to other MCP servers.

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

### Why This Architecture?

**Protocol Consistency**
- Everything speaks MCP - no mixing of protocols
- Dashboard → Orchestrator → MCP services (including Agent)
- Agent → Other MCP services

**Composability**
- Agent is just another service that can be:
  - Started/stopped like other services
  - Queried via standard MCP tools
  - Replaced or upgraded independently
  - Used by any MCP client

**Clean Separation**
- Data services (Kadaster, CBS, Rijkswaterstaat) → Pure data providers
- Agent service → Pure intelligent orchestrator
- No special case logic in the orchestrator

**Scalability**
- Each service can be scaled independently
- Agent can be containerized and deployed anywhere
- Multiple agents can coexist

### Components

**1. Agent Module (`client/agent.py`)**
- `GeospatialAgent` class that manages the interaction with Azure OpenAI
- Defines available tools (one for each MCP service)
- Handles the agent loop (tool use, result gathering, synthesis)

**2. Agent MCP Server (`mcp-servers/agent-service/server.py`)**

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

**3. Orchestrator Integration (`client/orchestrator.py`)**
- New endpoint: `POST /api/agent/ask`
- Bridges the agent to the MCP tool execution
- Handles authentication and error management
- Agent service configured in SERVICES dictionary

**4. Dashboard UI (`dashboard/index.html`)**
- Text area for natural language questions
- Real-time feedback during agent execution
- Formatted display of agent responses
- Agent appears as a service box with 🤖 icon

---

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

### Docker Configuration

The agent service requires specific Docker configuration:

```yaml
agent-service:
  build: ./mcp-servers/agent-service
  container_name: eai-agent-service
  env_file:
    - .env
  environment:
    - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
    - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
    - AZURE_OPENAI_DEPLOYMENT_NAME=${AZURE_OPENAI_DEPLOYMENT_NAME}
    - AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION}
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

---

## Example Agent Execution

**Question:** "What can you tell me about Amsterdam?"

**Agent's thinking process:**

1. **Initial analysis**: Amsterdam is mentioned, need comprehensive data
2. **Tool calls (parallel)**:
   - `query_kadaster` → Get property at LOC001
   - `query_cbs` → Get statistics for LOC001
   - `query_rijkswaterstaat` → Get infrastructure for LOC001
3. **Results received**:
   - Kadaster: Property owned by Gemeente Amsterdam, 450.5 m², office building from 1920
   - CBS: Population 872,680, avg income €38,500
   - Rijkswaterstaat: IJ-tunnel entrance, Damrak canal, A10 highway
4. **Synthesis**: Combines all data into comprehensive answer

**Answer:**
```
Amsterdam (location LOC001 at Damrak 1) is the capital and most populous city
in the Netherlands, with several notable characteristics:

Demographics (CBS):
- Population: 872,680 people
- Households: 465,242
- Average income: €38,500
- Population density: 5,135 people per km²
- Unemployment rate: 5.2%

Property Information (Kadaster):
- The property at Damrak 1 is registered under cadastral ID AMS01-G-1234
- Owner: Gemeente Amsterdam (City of Amsterdam)
- Surface area: 450.5 m²
- Land use: Commercial
- Building type: Office building
- Construction year: 1920

Infrastructure (Rijkswaterstaat):
- Major infrastructure: IJ-tunnel entrance (bridge), in good condition
- Water: Damrak canal with water level at 0.4 meters
- Roads: A10 highway (ring road), maximum speed 100 km/h, good condition

Amsterdam is characterized by high population density, historic commercial
properties, and well-maintained infrastructure including canals and modern
highways.
```

---

## Troubleshooting

### "AI Agent not available"
**Cause**: Azure OpenAI SDK not installed or credentials not configured

**Solution**:
```bash
uv sync
# Configure .env file with Azure OpenAI credentials
```

### "Maximum iterations reached"
**Cause**: Agent couldn't complete in 5 tool-use cycles

**Solution**: Simplify the question or increase `max_iterations` in the agent service code

### "Service not running"
**Cause**: Required MCP service is stopped

**Solution**: Start all services from the dashboard

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
- Simple queries: 2-4 seconds
- Multi-service queries: 4-8 seconds
- Complex synthesis: 6-10 seconds

**To investigate:**
```bash
# Watch agent logs in real-time
docker logs -f eai-agent-service
```

Look for which services are being called and how long each takes.

---

## Advanced Usage

### Custom Questions

The agent can handle various question formats:

**Comparison questions:**
```
"Compare Amsterdam and Rotterdam in terms of population and infrastructure"
```

**Analytical questions:**
```
"Which location has the best combination of low unemployment and good infrastructure?"
```

**Specific data retrieval:**
```
"What is the cadastral ID for the property in Utrecht?"
```

### Debugging

Enable debug logging in the agent service:

```python
# In agent-service/server.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check orchestrator logs:
```bash
tail -f /tmp/orchestrator.log | grep Agent
```

### Extending the Agent

**Add new capabilities:**

1. Add new tools to `AVAILABLE_TOOLS` in agent service
2. Implement the tool execution logic
3. Update the system prompt with tool descriptions

**Example: Add weather data**
```python
{
    "name": "query_weather",
    "description": "Get current weather conditions",
    "input_schema": {
        "type": "object",
        "properties": {
            "location_id": {"type": "string"}
        }
    }
}
```

---

## Performance & Optimization

### Response Times

**Typical performance:**
- Single service query: 2-4 seconds
- Multi-service query: 4-8 seconds
- Complex synthesis: 6-10 seconds

### Optimization Opportunities

**Caching:**
```python
@lru_cache(maxsize=100)
def get_cached_answer(question):
    return ask_question(question)
```

**Parallel Tool Calls:**
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

**Connection Pooling:**
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

**Pre-warming:**
- Cache frequently asked questions
- Pre-warm MCP service connections
- Implement streaming responses

---

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
- Max token limits in AI model calls
- No code execution - agent can only call predefined MCP tools

---

## Cost Considerations

The agent uses Azure OpenAI, which has API costs based on your deployment:
- Costs vary by model and region
- Check your Azure OpenAI pricing tier for specific rates

Typical token usage:
- Simple query (1 tool call): ~1,000-3,000 tokens
- Complex query (3 tool calls): ~5,000-10,000 tokens

---

## Limitations

1. **Data scope**: Limited to the three sample locations (Amsterdam, Utrecht, Rotterdam)
2. **Tool calls**: Maximum 5 iterations to prevent infinite loops
3. **API costs**: Each question uses Azure OpenAI API tokens
4. **Service availability**: All relevant MCP services must be running
5. **Language**: Currently optimized for English questions

---

## Future Enhancements

### 1. Agent Capabilities

**Streaming responses:**
```python
# Return partial results as they're generated
for chunk in openai_stream:
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

**Source citations:**
Link back to specific MCP service responses

**Visualization:**
Generate charts/graphs from numerical data

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

---

## References

- [Azure OpenAI Service Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure OpenAI Function Calling](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Docker Engine API - Attach to Container](https://docs.docker.com/engine/api/v1.43/#tag/Container/operation/ContainerAttach)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)

---

**Last Updated:** 2025-12-24
**Agent Model:** Azure OpenAI (GPT-4o or GPT-4o-mini)
**Architecture Type:** Meta-Agent Pattern (MCP Agent Server)
**Protocol:** Model Context Protocol (MCP)
**Transport:** stdio (JSON-RPC 2.0)
