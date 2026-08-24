"""Unit tests for AppleScript JSON parsers."""

from __future__ import annotations

from outlook_agent.domain import SpecialFolderType
from outlook_agent.providers.outlook.applescript.parsers import (
    parse_accounts,
    parse_email,
    parse_folders,
    parse_summaries,
    strip_html,
)


def test_parse_accounts() -> None:
    raw = '[{"account_id":"1","name":"Work","email_address":"me@x.com"}]'
    accounts = parse_accounts(raw)
    assert len(accounts) == 1
    assert accounts[0].account_id == "1"
    assert accounts[0].email_address == "me@x.com"


def test_parse_folders_special_type() -> None:
    raw = (
        '[{"folder_id":"10","name":"Inbox","account_id":"1","parent_id":"",'
        '"special_type":1,"message_count":5,"unread_count":2}]'
    )
    folders = parse_folders(raw)
    assert folders[0].special_type is SpecialFolderType.INBOX
    assert folders[0].unread_count == 2
    assert folders[0].parent_id is None


def test_parse_summaries_builds_ref() -> None:
    raw = (
        '[{"item_id":"100","folder_id":"10","conversation_id":"900","subject":"Hi",'
        '"sender_name":"Al","sender_address":"al@x.com","preview":"p","is_read":true,'
        '"received_at":"2026-01-02T03:04:05","sent_at":"","has_attachments":false}]'
    )
    summaries = parse_summaries(raw, account_id="1")
    s = summaries[0]
    assert s.ref.item_id == "100"
    assert s.ref.account_id == "1"
    assert s.ref.conversation_id == "900"
    assert s.is_read is True
    assert s.received_at is not None and s.received_at.year == 2026


def test_parse_email_falls_back_to_html_text() -> None:
    raw = (
        '{"item_id":"100","folder_id":"10","conversation_id":"","subject":"S",'
        '"sender_name":"A","sender_address":"a@x.com","is_read":false,'
        '"received_at":"","sent_at":"","has_attachments":false,'
        '"body_text":"","body_html":"<p>Hello <b>world</b></p>",'
        '"to":[{"name":"B","address":"b@x.com"}],"cc":[]}'
    )
    email = parse_email(raw, account_id="1")
    assert email.body_text == "Hello world"
    assert email.recipients[0].address == "b@x.com"


def test_parse_empty_array() -> None:
    assert parse_summaries("[]", account_id="1") == []
    assert parse_accounts("") == []


def test_strip_html() -> None:
    assert strip_html("<p>Hi<br>there</p>") == "Hi\nthere"
    assert strip_html("a&nbsp;&amp;&nbsp;b") == "a & b"
