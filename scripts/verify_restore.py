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
        finance = _finance_checks(connection)

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

    failures.extend(finance["failures"])

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
                "finance_counts": finance["counts"],
                "files_checked": len(rows),
                "upload_dir": os.fspath(uploads),
                "ok": not failures,
                "failures": failures,
            },
            ensure_ascii=False,
        )
    )
    return 1 if failures else 0


def _finance_checks(connection: "psycopg.Connection[object]") -> dict[str, object]:
    """Verify restored finance rows when the schema is present.

    Counts are reported separately from the legacy ``counts.txt`` contract so
    older backups keep restoring without a format change.
    """
    present = connection.execute(
        "SELECT to_regclass('public.finance_journal_line')"
    ).fetchone()[0]
    if present is None:
        return {"counts": {}, "failures": []}

    counts = {
        table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        for table in (
            "finance_settings",
            "finance_account",
            "finance_period",
            "finance_journal",
            "finance_journal_line",
            "finance_audit",
            "finance_grant",
        )
    }
    unbalanced = connection.execute(
        """SELECT count(*) FROM (
               SELECT journal_id FROM finance_journal_line
               GROUP BY journal_id
               HAVING sum(debit_irr) <> sum(credit_irr)
           ) AS unbalanced"""
    ).fetchone()[0]
    thin_journals = connection.execute(
        """SELECT count(*) FROM (
               SELECT j.id FROM finance_journal j
               LEFT JOIN finance_journal_line l ON l.journal_id = j.id
               GROUP BY j.id
               HAVING count(l.id) < 2
           ) AS thin"""
    ).fetchone()[0]
    failures: list[str] = []
    if unbalanced:
        failures.append(f"{unbalanced} restored journals are unbalanced")
    if thin_journals:
        failures.append(
            f"{thin_journals} restored journals have fewer than two lines"
        )
    return {"counts": counts, "failures": failures}


if __name__ == "__main__":
    raise SystemExit(main())
