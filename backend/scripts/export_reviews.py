"""Export reviews, with their findings, to a JSON file: what is worth keeping
past REVIEW_RETENTION_DAYS, before the nightly sweep deletes it.

usage: .venv/bin/python scripts/export_reviews.py --out reviews.json [--repository owner/name] [--older-than DAYS] [--database sqlite:///./reviews.db]

Every column of every selected review is written as it is stored (the quoted
evidence lines have been through redaction; patches were never stored), with
timestamps in ISO 8601. Runs from backend/ with the same .env as the app,
since the database path comes from it; --database overrides it.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402


def _plain(row) -> Dict[str, Any]:
    out = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        out[column.name] = value.isoformat() if isinstance(value, datetime) else value
    return out


async def export(database_url: Optional[str], out: Path, repository: Optional[str] = None,
                 older_than_days: Optional[int] = None, now: Optional[datetime] = None) -> int:
    from database.connection import close_db, init_db
    from database.models import Review
    factory = await init_db(database_url)
    try:
        stmt = select(Review).options(selectinload(Review.findings)).order_by(Review.created_at)
        if repository:
            stmt = stmt.where(Review.repository == repository)
        if older_than_days is not None:
            # the same seam services/retention.py has, so a test is not a date away from meaning something else
            stmt = stmt.where(Review.created_at < (now or datetime.now(timezone.utc)) - timedelta(days=older_than_days))
        async with factory() as session:
            reviews = list((await session.execute(stmt)).scalars().all())
            rows: List[Dict[str, Any]] = []
            for r in reviews:
                row = _plain(r)
                row["findings"] = [_plain(f) for f in r.findings]
                rows.append(row)
    finally:
        await close_db()
    out.write_text(json.dumps({"exported_at": datetime.now(timezone.utc).isoformat(), "reviews": rows}, indent=1), encoding="utf-8")
    return len(rows)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--older-than", type=int, metavar="DAYS")
    parser.add_argument("--database", help="database URL; the app's DATABASE_URL when omitted")
    args = parser.parse_args(argv[1:])
    count = asyncio.run(export(args.database, args.out, args.repository, args.older_than))
    print(f"{count} review(s) written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
