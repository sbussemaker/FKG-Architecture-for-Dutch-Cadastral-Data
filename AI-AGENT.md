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

## Architecture

### Components

**1. Agent Module (`client/agent.py`)**
- `GeospatialAgent` class that manages the interaction with Azure OpenAI
- Defines available tools (one for each MCP service)
- Handles the agent loop (tool use, result gathering, synthesis)

**2. Orchestrator Integration (`client/orchestrator.py`)**
- New endpoint: `POST /api/agent/ask`
- Bridges the agent to the MCP tool execution
- Handles authentication and error management

**3. Dashboard UI (`dashboard/index.html`)**
- Text area for natural language questions
- Real-time feedback during agent execution
- Formatted display of agent responses

### Tool Definitions

The agent has access to three high-level tools:

1. **query_kadaster**: Property ownership, cadastral data, buildings
2. **query_cbs**: Demographics, population, statistics
3. **query_rijkswaterstaat**: Infrastructure, roads, water management

Each tool can invoke specific MCP server tools based on the sub-tool parameter.

## Setup

### 1. Install Dependencies

```bash
cd /home/stefan/ais
uv sync  # or pip install -r pyproject.toml
```

This installs the Azure OpenAI SDK (`openai` package).

### 2. Configure Azure OpenAI

Configure your Azure OpenAI credentials in the `.env` file at the project root:

```bash
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

These environment variables will be automatically loaded by the orchestrator and passed to the agent service.

### 3. Start the Orchestrator

```bash
cd client
python orchestrator.py
```

The agent will be automatically available if the API key is set.

### 4. Start MCP Services

From the dashboard, start all three services:
- Kadaster
- CBS
- Rijkswaterstaat

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

## Agent Loop

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

## Limitations

1. **Data scope**: Limited to the three sample locations (Amsterdam, Utrecht, Rotterdam)
2. **Tool calls**: Maximum 5 iterations to prevent infinite loops
3. **API costs**: Each question uses Claude API tokens
4. **Service availability**: All relevant MCP services must be running
5. **Language**: Currently optimized for English questions

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

Enable debug logging to see the agent's tool calls:

```python
# In agent.py, the agent logs each tool call:
print(f"[Agent] Calling {tool_name} with input: {tool_input}")
```

Check orchestrator logs:
```bash
tail -f /tmp/orchestrator.log | grep Agent
```

### Extending the Agent

**Add new capabilities:**

1. Add new tools to `AVAILABLE_TOOLS` in `agent.py`
2. Implement the tool execution in `_execute_tool()`
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

## Troubleshooting

### "AI Agent not available"
**Cause**: Azure OpenAI SDK not installed or credentials not configured
**Solution**:
```bash
pip install openai
# Configure .env file with Azure OpenAI credentials
```

### "Maximum iterations reached"
**Cause**: Agent couldn't complete in 5 tool-use cycles
**Solution**: Simplify the question or increase `max_iterations` in `agent.py`

### "Service not running"
**Cause**: Required MCP service is stopped
**Solution**: Start all services from the dashboard

### Slow responses
**Cause**: API latency or multiple sequential tool calls
**Solution**: Normal for complex questions. Typically 3-10 seconds.

## Cost Considerations

The agent uses Azure OpenAI, which has API costs based on your Azure deployment:
- Costs vary by model and region
- Check your Azure OpenAI pricing tier for specific rates

Typical token usage:
- Simple query (1 tool call): ~1,000-3,000 tokens
- Complex query (3 tool calls): ~5,000-10,000 tokens

## Security

1. **API Credentials**: Never commit `.env` file with Azure OpenAI credentials to version control
2. **Input validation**: Agent endpoint validates questions
3. **Sandboxed execution**: Agent can only call predefined MCP tools
4. **No code execution**: Agent cannot execute arbitrary code

## Performance

**Response times:**
- Single service query: 2-4 seconds
- Multi-service query: 4-8 seconds
- Complex synthesis: 6-10 seconds

**Optimization opportunities:**
- Cache frequently asked questions
- Implement streaming responses
- Pre-warm MCP service connections

## Future Enhancements

1. **Streaming responses**: Show partial answers as they're generated
2. **Conversation memory**: Multi-turn conversations with context
3. **Source citations**: Link back to specific MCP service responses
4. **Visualization**: Generate charts/graphs from numerical data
5. **Real data integration**: Connect to actual Kadaster/CBS/Rijkswaterstaat APIs

## References

- [Azure OpenAI Service Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure OpenAI Function Calling](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/function-calling)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)

---

**Last Updated:** 2025-12-13
**Agent Model:** Azure OpenAI (GPT-4o or GPT-4o-mini)
