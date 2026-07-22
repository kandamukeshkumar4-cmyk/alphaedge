"""Scanner spec version history + rollback (research-only)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Scanner, ScannerVersion


async def archive_current_spec(db: AsyncSession, scanner: Scanner) -> ScannerVersion:
    """Append the live spec into scanner_versions under its current version.

    Idempotent: if that version row already exists, return it unchanged.
    """
    ver = int(scanner.version or 1)
    existing = await db.scalar(
        select(ScannerVersion).where(
            ScannerVersion.scanner_id == scanner.id,
            ScannerVersion.version == ver,
        )
    )
    if existing is not None:
        return existing
    row = ScannerVersion(
        scanner_id=scanner.id,
        version=ver,
        spec=dict(scanner.spec or {}),
    )
    db.add(row)
    await db.flush()
    return row


async def apply_spec_change(
    db: AsyncSession,
    scanner: Scanner,
    new_spec: dict[str, Any],
) -> Scanner:
    """Archive previous spec, bump version, replace live spec."""
    await archive_current_spec(db, scanner)
    scanner.spec = dict(new_spec)
    scanner.version = int(scanner.version or 1) + 1
    await db.flush()
    await db.refresh(scanner)
    return scanner


async def rollback_scanner_spec(
    db: AsyncSession,
    scanner: Scanner,
    version: int,
) -> Scanner:
    """Restore ``scanner.spec`` from a historical version row.

    Archives the current live spec when that version is not yet snapshotted,
    then restores the requested snapshot onto the live scanner.
    """
    hist = await db.scalar(
        select(ScannerVersion).where(
            ScannerVersion.scanner_id == scanner.id,
            ScannerVersion.version == int(version),
        )
    )
    if hist is None:
        raise LookupError(f"scanner version {version} not found")
    await archive_current_spec(db, scanner)
    scanner.spec = dict(hist.spec or {})
    scanner.version = int(hist.version)
    await db.flush()
    await db.refresh(scanner)
    return scanner
