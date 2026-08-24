"""Smoke tests for AppleScript builders — pure functions, no live Outlook needed.

They assert each builder emits a well-formed script so the string-assembly logic (escaping,
interpolation, JSON prelude) stays covered even though execution requires macOS.
"""

from __future__ import annotations

from outlook_agent.providers.outlook.applescript import scripts, scripts_pim, scripts_write


def _valid(script: str) -> bool:
    return isinstance(script, str) and "tell application" in script and script.strip() != ""


def test_read_builders() -> None:
    assert _valid(scripts.list_accounts_script())
    assert _valid(scripts.list_folders_script(None))
    assert _valid(scripts.list_folders_script("1"))
    assert _valid(scripts.list_emails_script("1", "10", limit=5, offset=0))
    assert _valid(scripts.search_emails_script("Entra", account_id="1", folder_id="10", limit=5))
    assert _valid(scripts.search_emails_script("Entra", account_id=None, folder_id=None, limit=5))
    assert _valid(scripts.get_email_script("10", "100"))
    assert _valid(scripts.list_conversation_script("900"))


def test_write_builders() -> None:
    assert _valid(scripts_write.create_draft_script("s", "b", to=["a@x.com"], cc=[], bcc=[]))
    assert _valid(scripts_write.create_draft_script("s", "<b>", to=[], cc=[], bcc=[], html=True))
    assert _valid(scripts_write.send_draft_script("1"))
    assert _valid(scripts_write.delete_message_script("1"))
    assert _valid(scripts_write.move_message_script("1", "2"))
    assert _valid(scripts_write.set_read_script("1", True))
    assert _valid(scripts_write.set_flag_script("1", False))
    assert _valid(scripts_write.set_categories_script("1", ["Red", "Blue"]))
    assert _valid(scripts_write.create_folder_script("N", None))
    assert _valid(scripts_write.create_folder_script("N", "5"))
    assert _valid(scripts_write.rename_folder_script("5", "N"))
    assert _valid(scripts_write.delete_folder_script("5"))
    assert _valid(scripts_write.empty_folder_script("5"))
    assert _valid(scripts_write.get_draft_script("1"))
    assert _valid(scripts_write.list_drafts_script(10))
    assert _valid(scripts_write.update_draft_script("1", "s", "b"))
    assert _valid(scripts_write.reply_draft_script("1", True, "hi"))
    assert _valid(scripts_write.forward_draft_script("1", ["a@x.com"], "hi"))
    assert _valid(scripts_write.move_to_special_script("1", 12))


def test_pim_builders() -> None:
    assert _valid(scripts_pim.list_calendars_script())
    assert _valid(scripts_pim.list_events_script(5))
    assert _valid(scripts_pim.get_event_script("1"))
    assert _valid(
        scripts_pim.create_event_script(
            "s", "2026-01-01T09:00:00", "2026-01-01T10:00:00", "loc", "b"
        )
    )
    assert _valid(scripts_pim.delete_event_script("1"))
    assert _valid(scripts_pim.list_contacts_script(5, None))
    assert _valid(scripts_pim.list_contacts_script(5, "al"))
    assert _valid(scripts_pim.get_contact_script("1"))
    assert _valid(scripts_pim.list_tasks_script(5, None))
    assert _valid(scripts_pim.get_task_script("1"))
    assert _valid(scripts_pim.list_notes_script(5, None))
    assert _valid(scripts_pim.get_note_script("1"))


def test_escaping_in_builders() -> None:
    # A subject with quotes must be escaped inside the emitted literal.
    script = scripts_write.create_draft_script('say "hi"', "body", to=[], cc=[], bcc=[])
    assert '\\"hi\\"' in script
