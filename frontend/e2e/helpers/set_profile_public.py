"""Harness-only: toggle users.profile_public on the isolated e2e SQLite DB."""
from __future__ import annotations

import sqlite3
import sys


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "usage: set_profile_public.py <db_path> <email> <0|1>",
            file=sys.stderr,
        )
        return 2
    db_path, email, flag_raw = sys.argv[1], sys.argv[2], sys.argv[3]
    flag = 1 if flag_raw in ("1", "true", "True", "yes") else 0
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            "UPDATE users SET profile_public = ? WHERE lower(email) = lower(?)",
            (flag, email),
        )
        con.commit()
        print(cur.rowcount)
        return 0 if cur.rowcount else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
