## Completed Tasks

- ✅ `agent-service/server.py` now dynamically discovers tools from MCP servers using "tools/list" method
- ✅ Added `.env` file with Azure OpenAI credentials and updated docker-compose.yml to load it
- ✅ Replaced Anthropic SDK with Azure OpenAI SDK

## Notes

- To use the system, fill in your Azure OpenAI credentials in the `.env` file:
  - AZURE_OPENAI_ENDPOINT
  - AZURE_OPENAI_API_KEY
  - AZURE_OPENAI_DEPLOYMENT_NAME
  - AZURE_OPENAI_API_VERSION (defaults to 2024-08-01-preview)
