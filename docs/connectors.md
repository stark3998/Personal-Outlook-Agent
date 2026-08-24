# Connectors

The platform integrates with external systems only through narrow interfaces, keeping the
core provider-agnostic and portable.

## Outlook providers (`OutlookProvider`)

Application services depend on the `OutlookProvider` protocol, never a concrete provider.
The active provider is chosen by `OUTLOOK_AGENT_PROVIDER`:

| Value | Provider | Requirement |
|-------|----------|-------------|
| `auto` (default) | COM on Windows, AppleScript on macOS | — |
| `applescript` | `OutlookAppleScriptProvider` | macOS + classic Outlook + Automation permission |
| `com` | `OutlookCOMProvider` | Windows + classic Outlook + `pywin32` |
| `ui` | `OutlookUIScriptingProvider` (placeholder) | New Outlook (not yet implemented) |

Providers advertise a **capability set**; services check capabilities before dispatch and
raise `CapabilityUnavailable` if unsupported. See [capabilities.md](capabilities.md),
[apple-script.md](apple-script.md), and [windows-com.md](windows-com.md).

## LLM connector — Microsoft Foundry (`LLMProvider`)

The intelligence layer reaches the model only through the `LLMProvider` protocol. The
Outlook providers never import it, and email content is wrapped as untrusted data before
it is sent.

`FoundryLLMProvider` calls the OpenAI-compatible chat-completions endpoint of a Foundry
deployment:

```
POST {FOUNDRY_ENDPOINT}/openai/deployments/{FOUNDRY_DEPLOYMENT}/chat/completions
     ?api-version={FOUNDRY_API_VERSION}
```

### Configuration

| Variable | Purpose |
|----------|---------|
| `FOUNDRY_ENDPOINT` | Foundry resource endpoint (e.g. `https://<name>.openai.azure.com`) |
| `FOUNDRY_DEPLOYMENT` | Model deployment name |
| `FOUNDRY_API_VERSION` | API version (default `2024-10-21`) |
| `FOUNDRY_AUTH_MODE` | `default` |
| `FOUNDRY_API_KEY` | API-key auth (sent as `api-key` header), **or** |
| `FOUNDRY_ACCESS_TOKEN` | Bearer-token auth (`Authorization: Bearer …`) |

If Foundry is not configured, intelligence endpoints return `503 llm_unavailable`. No
secrets are committed; provide them via environment or the macOS Keychain.

### Interface

```python
class LLMProvider(Protocol):
    async def complete(self, messages, *, temperature=0.2) -> str: ...
    async def summarize(self, text, *, instructions=None) -> str: ...
    async def classify(self, text, labels) -> str: ...
    async def extract(self, text, what) -> list[str]: ...
    async def generate_reply(self, context, instructions) -> str: ...
```

To use a different LLM backend, implement `LLMProvider` (or subclass `LLMBase` and provide
`complete`) and inject it via `build_container(llm=...)`.

## MCP client connectors

The MCP server (stdio) is itself a connector for MCP-capable clients — Claude Desktop,
VS Code, and Claude Code. See [mcp.md](mcp.md) for setup and the tool catalog.

## Adding a new provider

1. Implement the `OutlookProvider` protocol in a new package under
   `providers/outlook/<name>/` (keep all backend-specific code there).
2. Advertise the capabilities you support via `ProviderCapabilities`.
3. Register it in `providers/outlook/factory.py`.
4. No changes are needed in services, MCP, REST, or CLI — they depend only on the
   interface.
