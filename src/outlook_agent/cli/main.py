"""``outlook-agent`` command-line interface.

JSON-first for programmatic/agent use. Delegates to the same application services as the
MCP and REST interfaces via the shared container.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import typer
from pydantic import BaseModel

from outlook_agent.domain import EmailRef, ProviderName
from outlook_agent.main import build_container

app = typer.Typer(add_completion=False, help="Personal Outlook Agent CLI")


def _print(value: Any) -> None:
    if isinstance(value, BaseModel):
        typer.echo(value.model_dump_json(indent=2))
    elif isinstance(value, list):
        typer.echo(
            json.dumps(
                [v.model_dump(mode="json") if isinstance(v, BaseModel) else v for v in value],
                indent=2,
            )
        )
    else:
        typer.echo(json.dumps(value, indent=2))


@app.command()
def diagnostics() -> None:
    """Print a structured diagnostic report."""
    container = build_container()
    _print(asyncio.run(container.diagnostics.report()))


@app.command()
def accounts() -> None:
    """List Outlook accounts."""
    container = build_container()
    _print(asyncio.run(container.mail.list_accounts()))


@app.command()
def folders(account_id: str | None = typer.Option(None, "--account-id")) -> None:
    """List folders, optionally scoped to an account."""
    container = build_container()
    _print(asyncio.run(container.mail.list_folders(account_id)))


@app.command()
def emails(
    account_id: str = typer.Option(..., "--account-id"),
    folder_id: str = typer.Option(..., "--folder-id"),
    limit: int = typer.Option(25, "--limit"),
    offset: int = typer.Option(0, "--offset"),
) -> None:
    """List message summaries in a folder."""
    container = build_container()
    _print(
        asyncio.run(container.mail.list_emails(account_id, folder_id, limit=limit, offset=offset))
    )


@app.command()
def search(
    query: str = typer.Argument(...),
    account_id: str | None = typer.Option(None, "--account-id"),
    folder_id: str | None = typer.Option(None, "--folder-id"),
    limit: int = typer.Option(25, "--limit"),
) -> None:
    """Search messages by subject/sender/content."""
    container = build_container()
    _print(
        asyncio.run(
            container.mail.search_emails(
                query, account_id=account_id, folder_id=folder_id, limit=limit
            )
        )
    )


@app.command()
def read(
    item_id: str = typer.Argument(...),
    account_id: str = typer.Option(..., "--account-id"),
    folder_id: str = typer.Option(..., "--folder-id"),
) -> None:
    """Fetch a full message by id (requires account and folder context)."""
    container = build_container()
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    _print(asyncio.run(container.mail.get_email(ref)))


@app.command()
def thread(
    conversation_id: str = typer.Argument(...),
    account_id: str | None = typer.Option(None, "--account-id"),
) -> None:
    """Reconstruct and print a conversation thread."""
    container = build_container()
    _print(asyncio.run(container.threads.get_thread(conversation_id, account_id=account_id)))


@app.command()
def drafts(account_id: str = typer.Option(..., "--account-id"), limit: int = 25) -> None:
    """List saved drafts."""
    container = build_container()
    _print(asyncio.run(container.drafts.list_drafts(account_id, limit=limit)))


@app.command("prepare-send")
def prepare_send(
    draft_id: str = typer.Argument(...),
    account_id: str = typer.Option(..., "--account-id"),
) -> None:
    """Prepare a gated send; returns an approval token to confirm."""
    container = build_container()
    _print(asyncio.run(container.drafts.prepare_send(account_id, draft_id)))


@app.command()
def confirm(
    action_id: str = typer.Argument(...),
    token: str = typer.Option(..., "--token"),
) -> None:
    """Confirm and execute a prepared action."""
    container = build_container()
    _print(asyncio.run(container.actions.confirm(action_id, token)))


@app.command()
def cancel(action_id: str = typer.Argument(...)) -> None:
    """Cancel a pending action."""
    container = build_container()
    asyncio.run(container.actions.cancel(action_id))
    _print({"status": "cancelled"})


@app.command()
def pending() -> None:
    """List actions awaiting confirmation."""
    container = build_container()
    _print(asyncio.run(container.actions.pending()))


@app.command()
def events(account_id: str = typer.Option(..., "--account-id"), limit: int = 25) -> None:
    """List upcoming calendar events."""
    container = build_container()
    _print(asyncio.run(container.calendar.list_events(account_id, limit=limit)))


@app.command()
def contacts(account_id: str = typer.Option(..., "--account-id"), limit: int = 50) -> None:
    """List contacts."""
    container = build_container()
    _print(asyncio.run(container.contacts.list_contacts(account_id, limit=limit)))


@app.command()
def summarize(
    item_id: str = typer.Argument(...),
    account_id: str = typer.Option(..., "--account-id"),
    folder_id: str = typer.Option(..., "--folder-id"),
) -> None:
    """Summarize a message via the intelligence service."""
    container = build_container()
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    _print({"summary": asyncio.run(container.intelligence.summarize_email(ref))})


@app.command()
def sync(
    account_id: str = typer.Option(..., "--account-id"),
    folder_id: str = typer.Option(..., "--folder-id"),
    limit: int = typer.Option(200, "--limit"),
) -> None:
    """Sync a folder into the local SQLite cache/index."""
    from outlook_agent.storage.factory import build_sync_service

    container = build_container()
    service = build_sync_service(container.provider)
    _print(asyncio.run(service.sync_folder(account_id, folder_id, limit=limit)))


if __name__ == "__main__":
    app()
