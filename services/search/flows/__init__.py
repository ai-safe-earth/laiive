"""Prefect flows for the SEARCH service (Phase 5b, D17).

Thin HTTP clients of the public gateway's /api/admin/search/* — they add no
write path; the shared neo4j_writer stays the only one. Runs authenticate as
a Supabase admin service account (password grant, JWT minted per task).
"""
