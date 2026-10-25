from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg

TABLES = (
    "user",
    "gym",
    "athlete_profile",
    "body_analysis_file",
    "workout_program_version",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--upload-dir", required=True)
    parser.add_argument("--expected-counts")
    args = parser.parse_args()

    url = args.database_url.replace("+psycopg", "")
    uploads = Path(args.upload_dir)
    failures: list[str] = []

    with psycopg.connect(url) as connection:
        counts = {
            table: connection.execute(
                f'SELECT count(*) FROM "{table}"'
            ).fetchone()[0]
            for table in TABLES
        }
        rows = connection.execute(
            "SELECT stored_name, size_bytes FROM body_analysis_file"
        ).fetchall()

    if args.expected_counts:
        expected = [
            int(value.strip())
            for value in Path(args.expected_counts).read_text().splitlines()
            if value.strip()
        ]
        actual = [counts[table] for table in TABLES]
        if expected != actual:
            failures.append(
                f"count mismatch: expected {expected}, restored {actual}"
            )

    for stored_name, size_bytes in rows:
        if Path(stored_name).name != stored_name:
            failures.append(f"unsafe stored name: {stored_name}")
            continue
        path = uploads / stored_name
        if not path.is_file():
            failures.append(f"missing file: {stored_name}")
        elif path.stat().st_size != size_bytes:
            failures.append(
                f"size mismatch for {stored_name}: {path.stat().st_size} != {size_bytes}"
            )

    print(
        json.dumps(
            {
                "counts": counts,
                "files_checked": len(rows),
                "upload_dir": os.fspath(uploads),
                "ok": not failures,
                "failures": failures,
            },
            ensure_ascii=False,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
