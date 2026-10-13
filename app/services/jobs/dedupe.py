"""
Duplicate detection.

Priority order (first match wins):
    1. source + external_id
    2. url
    3. content_hash

Deterministic SQL only. No fuzzy matching here (that's Phase 5).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job


def find_existing(
    session: Session,
    *,
    source: str,
    external_id: Optional[str],
    url: Optional[str],
    content_hash_value: Optional[str],
) -> Optional[Job]:
    """
    Return an existing Job matching any dedupe key, or None.
    Checks in priority order; first hit wins.
    """
    # 1. source + external_id
    if external_id:
        stmt = select(Job).where(
            Job.source == source,
            Job.external_id == external_id,
        )
        found = session.execute(stmt).scalar_one_or_none()
        if found is not None:
            return found

    # 2. url
    if url:
        stmt = select(Job).where(Job.url == url)
        found = session.execute(stmt).scalar_one_or_none()
        if found is not None:
            return found

    # 3. content_hash
    if content_hash_value:
        stmt = select(Job).where(Job.content_hash == content_hash_value)
        found = session.execute(stmt).scalars().first()
        if found is not None:
            return found

    return None