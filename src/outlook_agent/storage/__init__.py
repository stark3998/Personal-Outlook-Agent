"""Storage layer — SQLite cache/index. Outlook remains the source of truth.

The database is a *cache and search index*, not the system of record. It is safe to delete
and rebuild via sync (Milestone 12).
"""
