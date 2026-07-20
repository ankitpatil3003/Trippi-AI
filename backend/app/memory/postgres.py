"""Optional Postgres helpers. v1 trip store remains in-memory; DATABASE_URL enables future persistence."""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def postgres_configured() -> bool:
    return bool(get_settings().database_url)


def describe_backend() -> str:
    if postgres_configured():
        return "postgres+pgvector configured (trip store still in-memory for v1 runtime)"
    return "in-memory seed retrieval (no DATABASE_URL)"
