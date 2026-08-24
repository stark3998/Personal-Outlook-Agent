# MCP integration

`outlook-agent-mcp` runs a [FastMCP](https://github.com/jlowin/fastmcp) server over
**stdio**. It requires no Microsoft connectors and no cloud authentication — it drives your
local desktop Outlook through the same application services as the REST API and CLI.

Tools are thin wrappers: each validates context and delegates to a service. No AppleScript
or COM runs in the MCP layer. Tool schemas are stable even when provider internals change.

## Client setup

### VS Code

Copy [`configs/vscode.mcp.json.example`](../configs/vscode.mcp.json.example) to
`.vscode/mcp.json`:

```json
{
  "servers": {
    "outlook": { "type": "stdio", "command": "outlook-agent-mcp",
      "env": { "OUTLOOK_AGENT_PROVIDER": "auto" } }
  }
}
```

Configure tool approval so that **read** tools are auto-allowed and **write / gated**
tools always prompt.

### Claude Desktop

Merge [`configs/claude_desktop.json.example`](../configs/claude_desktop.json.example) into
`claude_desktop_config.json`:

```json
{ "mcpServers": { "outlook": { "command": "outlook-agent-mcp" } } }
```

### Claude Code

```bash
bash scripts/install_claude_mcp.sh      # claude mcp add outlook -- outlook-agent-mcp
```

## Tool catalog

### Diagnostics & read
| Tool | Arguments |
|------|-----------|
| `outlook_diagnostics` | — |
| `outlook_list_accounts` | — |
| `outlook_list_folders` | `account_id?` |
| `outlook_list_emails` | `account_id`, `folder_id`, `limit=25`, `offset=0` |
| `outlook_search_emails` | `query`, `account_id?`, `folder_id?`, `limit=25` |
| `outlook_get_email` | `item_id`, `account_id`, `folder_id`, `conversation_id?` |
| `outlook_get_thread` | `conversation_id`, `account_id?` |

### Drafts & organize
| Tool | Arguments |
|------|-----------|
| `outlook_list_drafts` | `account_id`, `limit=25` |
| `outlook_create_draft` | `account_id`, `subject`, `body`, `to?`, `cc?` |
| `outlook_reply` | `account_id`, `folder_id`, `item_id`, `body?`, `reply_all=false` |
| `outlook_mark_read` | `account_id`, `folder_id`, `item_id`, `read=true` (direct write) |

### Gated writes (return an approval token)
| Tool | Arguments |
|------|-----------|
| `outlook_prepare_send` | `account_id`, `draft_id` |
| `outlook_prepare_delete` | `account_id`, `folder_id`, `item_id` |
| `outlook_prepare_move` | `account_id`, `folder_id`, `item_id`, `target_folder_id` |

### Approvals
| Tool | Arguments |
|------|-----------|
| `outlook_pending_actions` | — |
| `outlook_confirm_action` | `action_id`, `token` |
| `outlook_cancel_action` | `action_id` |

### PIM
| Tool | Arguments |
|------|-----------|
| `outlook_list_events` | `account_id`, `limit=25` |
| `outlook_list_contacts` | `account_id`, `limit=50` |
| `outlook_list_tasks` | `account_id`, `limit=50` |

### Agent intelligence
| Tool | Arguments |
|------|-----------|
| `agent_summarize_email` | `account_id`, `folder_id`, `item_id` |
| `agent_summarize_inbox` | `account_id`, `folder_id`, `limit=20` |
| `agent_extract_action_items` | `account_id`, `folder_id`, `item_id` |
| `agent_prepare_reply` | `account_id`, `folder_id`, `item_id`, `instructions`, `create_draft=false` |
| `agent_find_unanswered` | `account_id`, `folder_id`, `limit=50` |
| `agent_find_followups` | `account_id`, `sent_folder_id`, `limit=50` |
| `agent_find_promised_actions` | `account_id`, `sent_folder_id`, `limit=25` |
| `agent_meeting_prep` | `account_id`, `event_id` |

## Gated flow from an MCP client

1. Call a `prepare_*` tool → receive `{ action_id, token, risk_level, summary, expires_at }`.
2. Show the user the summary/risk and get explicit confirmation.
3. Call `outlook_confirm_action` with `action_id` + `token` to execute.

The LLM can only *propose* actions; it cannot confirm without the token, and the target
must be unchanged since preparation.
