# Connectors

The platform integrates with external systems only through narrow interfaces, keeping the
core provider-agnostic and portable.

## Outlook providers (`OutlookProvider`)

Application services depend on the `OutlookProvider` protocol, never a concrete provider.
The active provider is chosen by `OUTLOOK_AGENT_PROVIDER`:

| Value | Provider | Requirement |
|-------|----------|-------------|
| `auto` (default) | COM on Windows, AppleScript on macOS | — |
| `applescript` | `OutlookAppleScriptProvider` | macOS + Classic Outlook + Automation permission |
| `com` | `OutlookCOMProvider` | Windows + Classic Outlook + `pywin32` |
| `ui` | `OutlookUIScriptingProvider` (placeholder) | not yet implemented |

Providers advertise a **capability set**; services check capabilities before dispatch and
raise `CapabilityUnavailable` if unsupported. See [capabilities.md](capabilities.md),
[apple-script.md](apple-script.md), and [windows-com.md](windows-com.md).

## LLM connector — Microsoft Foundry / Azure OpenAI (`LLMProvider`)

The intelligence layer reaches the model only through the `LLMProvider` protocol. The
Outlook providers never import it, and email content is wrapped as untrusted data before
it is sent to the LLM.

### Implementation

`FoundryLLMProvider` uses `openai.AsyncAzureOpenAI` to call the **chat completions**
endpoint of a Foundry/Azure OpenAI deployment:

```
POST {FOUNDRY_ENDPOINT}/openai/deployments/{FOUNDRY_DEPLOYMENT}/chat/completions
     ?api-version={FOUNDRY_API_VERSION}
```

> **Why not the Agent Framework SDK?** The Agent Framework `OpenAIChatClient` (v1.14.0)
> targets the newer Responses API (`/responses`). Some Azure OpenAI resources do not yet
> support that endpoint and return `400 BadRequest: API version not supported`. The chat
> completions path is universally available on all Azure OpenAI resources. We therefore
> use `openai.AsyncAzureOpenAI` directly.

### Configuration

All Foundry vars are loaded from `.env` via the `Settings` model (with `AliasChoices` so
they work without the `OUTLOOK_AGENT_` prefix):

| Variable | Purpose |
|----------|---------|
| `FOUNDRY_ENDPOINT` | Azure OpenAI resource endpoint, e.g. `https://<name>.openai.azure.com` |
| `FOUNDRY_DEPLOYMENT` | Model deployment name |
| `FOUNDRY_API_VERSION` | API version (default `2024-10-21`; `2024-12-01-preview` also verified) |
| `FOUNDRY_API_KEY` | API-key auth (sent as `api-key` header) |
| `FOUNDRY_ACCESS_TOKEN` | Bearer-token auth (`Authorization: Bearer …`) — used if `FOUNDRY_API_KEY` is absent |

If neither key nor token is set, intelligence endpoints return `503 llm_unavailable`.
Credentials are never committed; provide them via `.env` or the macOS Keychain.

### Loading mechanism

`FoundryConfig` is constructed in `main.py:build_container()` with values sourced from
`Settings`:

```python
foundry_cfg = FoundryConfig(
    endpoint=settings.foundry_endpoint,
    deployment=settings.foundry_deployment,
    api_version=settings.foundry_api_version,
    api_key=settings.foundry_api_key or settings.foundry_access_token,
)
llm = FoundryLLMProvider(foundry_cfg)
```

`Settings` uses `pydantic-settings` with `AliasChoices` so `FOUNDRY_ENDPOINT` (without the
`OUTLOOK_AGENT_` prefix) is loaded correctly from `.env`.

### LLMProvider interface

```python
class LLMProvider(Protocol):
    async def complete(self, messages: list[LLMMessage], *, temperature=0.2) -> str: ...
    async def summarize(self, text: str, *, instructions=None) -> str: ...
    async def classify(self, text: str, labels: list[str]) -> str: ...
    async def extract(self, text: str, what: str) -> list[str]: ...
    async def generate_reply(self, context: str, instructions: str) -> str: ...
```

To use a different LLM backend, implement `LLMProvider` (or subclass `LLMBase` and override
`complete`) and inject it via `build_container(llm=...)`.

## MCP client connectors

The MCP server (stdio) is itself a connector for MCP-capable clients — Claude Desktop,
VS Code, and Claude Code. See [mcp.md](mcp.md) for setup and the full tool catalog.

## Adding a new Outlook provider

1. Implement the `OutlookProvider` protocol in a new package under
   `providers/outlook/<name>/` (keep all backend-specific code there).
2. Advertise the capabilities you support via `ProviderCapabilities`.
3. Register it in `providers/outlook/factory.py`.
4. No changes are needed in services, MCP, REST, or CLI — they depend only on the protocol.
