"""New Outlook UI-scripting provider (placeholder).

New Outlook exposes a drastically reduced AppleScript dictionary; this provider will use
macOS UI/Accessibility automation as a fallback (Milestone 13, techniques adapted from
Aanerud/outlook-desktop-mcp). UI selectors and the accessibility hierarchy stay isolated
here and must never leak into MCP/REST schemas.
"""
