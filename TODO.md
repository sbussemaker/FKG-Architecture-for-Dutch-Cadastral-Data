## Completed Tasks

- ✅ `agent-service/server.py` now dynamically discovers tools from MCP servers using "tools/list" method
- ✅ Added `.env` file with Azure OpenAI credentials and updated docker-compose.yml to load it
- ✅ Replaced Anthropic SDK with Azure OpenAI SDK
- ✅ `.env` variables are now passed to agent service in orchestrator.py
- ✅ Updated all documentation (README.md, AGENTS.md) from Anthropic to Azure OpenAI
- ✅ Replaced all print statements with proper logging in agent-service/server.py
- ✅ Added strict system prompt to prevent AI from making guesses (only uses tool data)
- ✅ Added LOG_LEVEL environment variable for configurable logging (DEBUG, INFO, WARNING, ERROR)
- ✅ Updated orchestrator.py to respect LOG_LEVEL from .env file
- ✅ Reduced Flask/werkzeug logging noise (only shows warnings/errors)

## Notes

- To use the system, fill in your Azure OpenAI credentials in the `.env` file:
  - AZURE_OPENAI_ENDPOINT
  - AZURE_OPENAI_API_KEY
  - AZURE_OPENAI_DEPLOYMENT_NAME
  - AZURE_OPENAI_API_VERSION (defaults to 2024-12-01-preview)
  - LOG_LEVEL (optional, defaults to INFO - can be DEBUG, INFO, WARNING, ERROR, CRITICAL)
