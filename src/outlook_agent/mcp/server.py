"""FastMCP server exposing the read-only Outlook tools.

Tools are intentionally thin: each one validates/looks up context and delegates to a
service. No AppleScript runs here. Write/destructive tools are added in later milestones
behind the ActionService.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from outlook_agent.domain import DraftBody, DraftInput, EmailRef, ProviderName, Recipient
from outlook_agent.main import Container, build_container

mcp: FastMCP = FastMCP("personal-outlook-agent")
_container: Container = build_container()


@mcp.tool
async def outlook_diagnostics() -> dict[str, Any]:
    """Report Outlook install/running state, permissions, and provider capabilities."""
    report = await _container.diagnostics.report()
    return report.model_dump(mode="json")


@mcp.tool
async def outlook_list_accounts() -> list[dict[str, Any]]:
    """List the configured Outlook accounts."""
    accounts = await _container.mail.list_accounts()
    return [a.model_dump(mode="json") for a in accounts]


@mcp.tool
async def outlook_list_folders(account_id: str | None = None) -> list[dict[str, Any]]:
    """List mail folders, optionally scoped to a single account id."""
    folders = await _container.mail.list_folders(account_id)
    return [f.model_dump(mode="json") for f in folders]


@mcp.tool
async def outlook_list_emails(
    account_id: str, folder_id: str, limit: int = 25, offset: int = 0
) -> list[dict[str, Any]]:
    """List message summaries in a folder (newest first)."""
    summaries = await _container.mail.list_emails(account_id, folder_id, limit=limit, offset=offset)
    return [s.model_dump(mode="json") for s in summaries]


@mcp.tool
async def outlook_search_emails(
    query: str,
    account_id: str | None = None,
    folder_id: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Search Outlook messages by subject/sender/content."""
    summaries = await _container.mail.search_emails(
        query, account_id=account_id, folder_id=folder_id, limit=limit
    )
    return [s.model_dump(mode="json") for s in summaries]


@mcp.tool
async def outlook_get_email(
    item_id: str, account_id: str, folder_id: str, conversation_id: str | None = None
) -> dict[str, Any]:
    """Fetch a full message. Account and folder context are required to resolve identity."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
        conversation_id=conversation_id,
    )
    email = await _container.mail.get_email(ref)
    return email.model_dump(mode="json")


@mcp.tool
async def outlook_get_thread(conversation_id: str, account_id: str | None = None) -> dict[str, Any]:
    """Return the reconstructed thread for a conversation id."""
    thread = await _container.threads.get_thread(conversation_id, account_id=account_id)
    return thread.model_dump(mode="json")


# --- Drafts & sending (send is gated) ------------------------------------------------


@mcp.tool
async def outlook_list_drafts(account_id: str, limit: int = 25) -> list[dict[str, Any]]:
    """List saved drafts."""
    drafts = await _container.drafts.list_drafts(account_id, limit=limit)
    return [d.model_dump(mode="json") for d in drafts]


@mcp.tool
async def outlook_create_draft(
    account_id: str,
    subject: str,
    body: str,
    to: list[str] | None = None,
    cc: list[str] | None = None,
) -> dict[str, Any]:
    """Create a draft message (does not send)."""
    data = DraftInput(
        subject=subject,
        body=DraftBody(text=body),
        to=[Recipient(address=a) for a in (to or [])],
        cc=[Recipient(address=a) for a in (cc or [])],
    )
    draft = await _container.drafts.create_draft(account_id, data)
    return draft.model_dump(mode="json")


@mcp.tool
async def outlook_reply(
    account_id: str,
    folder_id: str,
    item_id: str,
    body: str | None = None,
    reply_all: bool = False,
) -> dict[str, Any]:
    """Create a reply/reply-all draft for a message (does not send)."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    draft = await _container.drafts.reply(ref, reply_all=reply_all, body=body)
    return draft.model_dump(mode="json")


@mcp.tool
async def outlook_prepare_send(account_id: str, draft_id: str) -> dict[str, Any]:
    """Prepare a gated send. Returns an approval token; confirm with outlook_confirm_action."""
    token = await _container.drafts.prepare_send(account_id, draft_id)
    return token.model_dump(mode="json")


# --- Gated organization ---------------------------------------------------------------


@mcp.tool
async def outlook_prepare_delete(account_id: str, folder_id: str, item_id: str) -> dict[str, Any]:
    """Prepare a gated delete of a message. Confirm with outlook_confirm_action."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    token = await _container.mail.prepare_delete(ref)
    return token.model_dump(mode="json")


@mcp.tool
async def outlook_prepare_move(
    account_id: str, folder_id: str, item_id: str, target_folder_id: str
) -> dict[str, Any]:
    """Prepare a gated move of a message. Confirm with outlook_confirm_action."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    token = await _container.mail.prepare_move(ref, target_folder_id)
    return token.model_dump(mode="json")


@mcp.tool
async def outlook_mark_read(
    account_id: str, folder_id: str, item_id: str, read: bool = True
) -> dict[str, str]:
    """Mark a message read or unread (low-risk direct write)."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    await _container.mail.mark_read(ref, read=read)
    return {"status": "ok"}


# --- Action confirmation --------------------------------------------------------------


@mcp.tool
async def outlook_pending_actions() -> list[dict[str, Any]]:
    """List actions awaiting confirmation."""
    return [a.model_dump(mode="json") for a in await _container.actions.pending()]


@mcp.tool
async def outlook_confirm_action(action_id: str, token: str) -> dict[str, Any]:
    """Confirm and execute a prepared action using its approval token."""
    result = await _container.actions.confirm(action_id, token)
    return result.model_dump(mode="json")


@mcp.tool
async def outlook_cancel_action(action_id: str) -> dict[str, str]:
    """Cancel a pending action."""
    await _container.actions.cancel(action_id)
    return {"status": "cancelled"}


# --- Calendar / contacts / tasks / notes (read) ---------------------------------------


@mcp.tool
async def outlook_list_events(account_id: str, limit: int = 25) -> list[dict[str, Any]]:
    """List upcoming calendar events."""
    events = await _container.calendar.list_events(account_id, limit=limit)
    return [e.model_dump(mode="json") for e in events]


@mcp.tool
async def outlook_list_contacts(account_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """List contacts."""
    contacts = await _container.contacts.list_contacts(account_id, limit=limit)
    return [c.model_dump(mode="json") for c in contacts]


@mcp.tool
async def outlook_list_tasks(account_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """List tasks."""
    tasks = await _container.tasks.list_tasks(account_id, limit=limit)
    return [t.model_dump(mode="json") for t in tasks]


# --- Agent intelligence ---------------------------------------------------------------


@mcp.tool
async def agent_summarize_email(account_id: str, folder_id: str, item_id: str) -> dict[str, str]:
    """Summarize a message."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    return {"summary": await _container.intelligence.summarize_email(ref)}


@mcp.tool
async def agent_extract_action_items(
    account_id: str, folder_id: str, item_id: str
) -> dict[str, Any]:
    """Extract action items from a message."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    return (await _container.intelligence.extract_action_items(ref)).model_dump(mode="json")


@mcp.tool
async def agent_prepare_reply(
    account_id: str,
    folder_id: str,
    item_id: str,
    instructions: str,
    create_draft: bool = False,
) -> dict[str, Any]:
    """Generate a reply proposal (optionally saved as a draft). Never sends."""
    ref = EmailRef(
        provider=ProviderName.OUTLOOK_APPLESCRIPT,
        account_id=account_id,
        folder_id=folder_id,
        item_id=item_id,
    )
    proposal = await _container.intelligence.prepare_reply(
        ref, instructions, create_draft=create_draft
    )
    return proposal.model_dump(mode="json")


@mcp.tool
async def agent_summarize_inbox(account_id: str, folder_id: str, limit: int = 20) -> dict[str, str]:
    """Summarize the most recent messages in a folder into an inbox digest."""
    summary = await _container.intelligence.summarize_inbox(account_id, folder_id, limit=limit)
    return {"summary": summary}


@mcp.tool
async def agent_find_unanswered(
    account_id: str, folder_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Find inbox messages from others that have no later reply from me."""
    found = await _container.intelligence.find_unanswered(account_id, folder_id, limit=limit)
    return [s.model_dump(mode="json") for s in found]


@mcp.tool
async def agent_find_followups(
    account_id: str, sent_folder_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Find messages I sent that are the latest in their thread (awaiting a reply)."""
    found = await _container.intelligence.find_followups(account_id, sent_folder_id, limit=limit)
    return [s.model_dump(mode="json") for s in found]


@mcp.tool
async def agent_find_promised_actions(
    account_id: str, sent_folder_id: str, limit: int = 25
) -> dict[str, Any]:
    """Detect commitments I made in recently sent mail."""
    items = await _container.intelligence.find_promised_actions(
        account_id, sent_folder_id, limit=limit
    )
    return {"promised_actions": items}


@mcp.tool
async def agent_meeting_prep(account_id: str, event_id: str) -> dict[str, Any]:
    """Assemble a briefing for an upcoming event from related mail."""
    prep = await _container.intelligence.meeting_prep(account_id, event_id)
    return prep.model_dump(mode="json")


def main() -> None:
    """Entry point for ``outlook-agent-mcp``: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
