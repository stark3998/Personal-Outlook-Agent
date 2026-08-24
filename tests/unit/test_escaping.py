"""Unit tests for AppleScript escaping."""

from __future__ import annotations

from outlook_agent.providers.outlook.applescript.executor import escape, quote


def test_escape_quotes_and_backslashes() -> None:
    assert escape('a"b\\c') == 'a\\"b\\\\c'


def test_escape_newlines_become_concatenation() -> None:
    assert escape("line1\nline2") == 'line1" & linefeed & "line2'
    assert escape("a\r\nb") == 'a" & linefeed & "b'


def test_quote_wraps_in_literal() -> None:
    assert quote("hi") == '"hi"'
    assert quote('say "hi"') == '"say \\"hi\\""'


def test_escape_prevents_literal_break() -> None:
    # A closing quote inside the value must be escaped so it cannot terminate the literal.
    malicious = '"; do shell script "rm -rf /"'
    escaped = escape(malicious)
    assert '"' not in escaped.replace('\\"', "")
