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

PLATFORM_TABLES = (
    "platform_agreement",
    "platform_receivable",
    "platform_credit",
    "platform_credit_application",
    "platform_invoice",
    "platform_invoice_line",
    "platform_invoice_cancellation",
    "platform_invoice_line_reversal",
    "platform_payment",
    "platform_payment_allocation",
    "platform_journal",
    "platform_journal_line",
    "platform_sequence",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--upload-dir", required=True)
    parser.add_argument("--expected-counts")
    parser.add_argument("--expected-platform-counts")
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
        platform = _platform_checks(connection)

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

    if args.expected_platform_counts:
        if not platform["counts"]:
            failures.append(
                "platform schema missing in restored database"
            )
        else:
            expected_platform = [
                int(value.strip())
                for value in Path(args.expected_platform_counts).read_text().splitlines()
                if value.strip()
            ]
            actual_platform = [
                platform["counts"][table] for table in PLATFORM_TABLES
            ]
            if expected_platform != actual_platform:
                failures.append(
                    "platform count mismatch: "
                    f"expected {expected_platform}, restored {actual_platform}"
                )

    failures.extend(finance["failures"])
    failures.extend(platform["failures"])

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
                "platform_counts": platform["counts"],
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




def _platform_checks(connection: "psycopg.Connection[object]") -> dict[str, object]:
    """Verify restored platform ledger and billing facts when present."""
    present = connection.execute(
        "SELECT to_regclass('public.platform_journal_line')"
    ).fetchone()[0]
    if present is None:
        return {"counts": {}, "failures": []}

    counts = {
        table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        for table in PLATFORM_TABLES
    }
    failures: list[str] = []
    unbalanced = connection.execute(
        """SELECT count(*) FROM (
               SELECT journal_id FROM platform_journal_line
               GROUP BY journal_id
               HAVING sum(debit_irr) <> sum(credit_irr)
           ) AS unbalanced"""
    ).fetchone()[0]
    if unbalanced:
        failures.append(f"{unbalanced} restored platform journals are unbalanced")
    thin = connection.execute(
        """SELECT count(*) FROM (
               SELECT j.id FROM platform_journal j
               LEFT JOIN platform_journal_line l ON l.journal_id = j.id
               GROUP BY j.id
               HAVING count(l.id) < 2
           ) AS thin"""
    ).fetchone()[0]
    if thin:
        failures.append(
            f"{thin} restored platform journals have fewer than two lines"
        )
    bad_payments = connection.execute(
        """SELECT count(*) FROM platform_payment p
           WHERE p.amount_irr <> COALESCE((
             SELECT sum(a.amount_irr) FROM platform_payment_allocation a
             WHERE a.payment_id = p.id
           ), 0)"""
    ).fetchone()[0]
    if bad_payments:
        failures.append(
            f"{bad_payments} platform payments do not match allocations"
        )
    mismatched_allocations = connection.execute(
        """SELECT count(*) FROM platform_payment_allocation a
           JOIN platform_payment p ON p.id = a.payment_id
           JOIN platform_invoice_line l ON l.id = a.invoice_line_id
           WHERE l.invoice_id <> p.invoice_id"""
    ).fetchone()[0]
    if mismatched_allocations:
        failures.append(
            f"{mismatched_allocations} platform allocations reference a "
            "different invoice than their payment"
        )
    bad_line_paid = connection.execute(
        """SELECT count(*) FROM platform_invoice_line l
           WHERE l.paid_irr <> COALESCE((
             SELECT sum(a.amount_irr) FROM platform_payment_allocation a
             WHERE a.invoice_line_id = l.id
           ), 0)"""
    ).fetchone()[0]
    if bad_line_paid:
        failures.append(
            f"{bad_line_paid} platform invoice lines have a paid amount "
            "that does not match their allocations"
        )
    overpaid_receivables = connection.execute(
        "SELECT count(*) FROM platform_receivable WHERE paid_irr > amount_irr"
    ).fetchone()[0]
    if overpaid_receivables:
        failures.append(
            f"{overpaid_receivables} platform receivables are overpaid"
        )
    overpaid_lines = connection.execute(
        "SELECT count(*) FROM platform_invoice_line WHERE paid_irr > amount_irr"
    ).fetchone()[0]
    if overpaid_lines:
        failures.append(
            f"{overpaid_lines} platform invoice lines are overpaid"
        )
    cross_gym_credits = connection.execute(
        """SELECT count(*) FROM platform_credit_application ca
           JOIN platform_credit c ON c.id = ca.credit_id
           JOIN platform_invoice_line l ON l.id = ca.invoice_line_id
           WHERE c.gym_id <> l.gym_id"""
    ).fetchone()[0]
    if cross_gym_credits:
        failures.append(
            f"{cross_gym_credits} platform credit applications cross gyms"
        )
    over_applied_credits = connection.execute(
        """SELECT count(*) FROM (
               SELECT c.id FROM platform_credit c
               JOIN platform_credit_application ca ON ca.credit_id = c.id
               GROUP BY c.id, c.amount_irr
               HAVING sum(ca.amount_irr) > c.amount_irr
           ) AS bad"""
    ).fetchone()[0]
    if over_applied_credits:
        failures.append(
            f"{over_applied_credits} platform credits are over-applied"
        )
    invoice_sequences = connection.execute(
        """SELECT count(*) FROM platform_invoice i
           WHERE i.invoice_number > COALESCE((
             SELECT last_value FROM platform_sequence
             WHERE doc_type = 'PLATFORM_INVOICE'
           ), 0)"""
    ).fetchone()[0]
    if invoice_sequences:
        failures.append(
            f"{invoice_sequences} platform invoices exceed their sequence"
        )
    journal_sequences = connection.execute(
        """SELECT count(*) FROM platform_journal j
           WHERE j.entry_number > COALESCE((
             SELECT last_value FROM platform_sequence
             WHERE doc_type = 'PLATFORM_JOURNAL'
           ), 0)"""
    ).fetchone()[0]
    if journal_sequences:
        failures.append(
            f"{journal_sequences} platform journals exceed their sequence"
        )
    return {"counts": counts, "failures": failures}

if __name__ == "__main__":
    raise SystemExit(main())
