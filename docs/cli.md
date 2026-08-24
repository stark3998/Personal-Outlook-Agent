# CLI reference

`outlook-agent` is a Typer CLI over the same application services as the MCP and REST
interfaces. Output is **JSON-first** for programmatic/agent use.

```bash
outlook-agent --help
outlook-agent <command> [OPTIONS]
```

## Read

| Command | Options |
|---------|---------|
| `diagnostics` | — |
| `accounts` | — |
| `folders` | `--account-id` |
| `emails` | `--account-id`, `--folder-id`, `--limit`, `--offset` |
| `search <query>` | `--account-id`, `--folder-id`, `--limit` |
| `read <item_id>` | `--account-id`, `--folder-id` |
| `thread <conversation_id>` | `--account-id` |

## Drafts & approvals

| Command | Options |
|---------|---------|
| `drafts` | `--account-id`, `--limit` |
| `prepare-send <draft_id>` | `--account-id` → prints an approval token |
| `pending` | — |
| `confirm <action_id>` | `--token` |
| `cancel <action_id>` | — |

## Calendar / contacts

| Command | Options |
|---------|---------|
| `events` | `--account-id`, `--limit` |
| `contacts` | `--account-id`, `--limit` |

## Agent intelligence

| Command | Options |
|---------|---------|
| `summarize <item_id>` | `--account-id`, `--folder-id` |
| `summarize-inbox` | `--account-id`, `--folder-id`, `--limit` |
| `unanswered` | `--account-id`, `--folder-id`, `--limit` |
| `followups` | `--account-id`, `--sent-folder-id`, `--limit` |
| `meeting-prep <event_id>` | `--account-id` |

## Sync

| Command | Options |
|---------|---------|
| `sync` | `--account-id`, `--folder-id`, `--limit`, `--incremental`, `--detect-deletions` |

## Examples

```bash
outlook-agent diagnostics
outlook-agent search "Entra" --limit 10
outlook-agent read 100 --account-id 1 --folder-id 10

# gated send
TOKEN=$(outlook-agent prepare-send 200 --account-id 1)   # prints { action_id, token, ... }
outlook-agent confirm <action_id> --token <token>

# incremental sync into the local cache/index
outlook-agent sync --account-id 1 --folder-id 10 --incremental --detect-deletions
```

> The gated flow works across CLI/API processes only when the persistent store is enabled
> (`OUTLOOK_AGENT_APPROVAL_STORE=sqlite`); otherwise `prepare` and `confirm` must occur in
> the same process.
