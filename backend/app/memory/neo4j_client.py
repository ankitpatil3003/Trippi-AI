"""Optional Neo4j client. Hybrid retrieval uses in-memory neighborhood graph when Neo4j is unset."""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def neo4j_configured() -> bool:
    settings = get_settings()
    return bool(settings.neo4j_uri and settings.neo4j_password)


def describe_backend() -> str:
    if neo4j_configured():
        return "neo4j uri configured (v1 expand uses in-memory neighborhood links + seed)"
    return "in-memory neighborhood graph"
