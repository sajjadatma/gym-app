#!/usr/bin/env bash
# Backup a running Compose deployment (PostgreSQL + uploads) without exposing
# the database port. Intended for cron/systemd on the deployment host.
#
# Required: DEPLOY_ENV (staging|production|ci). Optional: ENV_FILE, BACKUP_DIR,
# BACKUP_RETENTION_DAYS, BACKUP_RCLONE_REMOTE.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEPLOY_ENV="${DEPLOY_ENV:?DEPLOY_ENV must be staging, production or ci}"
COMPOSE=(docker compose)
if [ -n "${ENV_FILE:-}" ] && [ -f "$ENV_FILE" ]; then
  COMPOSE+=(--env-file "$ENV_FILE")
fi
COMPOSE+=(-f compose.deploy.yml -f "compose.$DEPLOY_ENV.yml")

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
POSTGRES_DB="${POSTGRES_DB:-app}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
umask 077

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/$STAMP"
mkdir -p "$TARGET"
chmod 700 "$BACKUP_DIR" "$TARGET"

echo "Backing up database..." >&2
"${COMPOSE[@]}" exec -T db pg_dump -U postgres -Fc --no-owner --no-privileges \
  "$POSTGRES_DB" > "$TARGET/db.dump"
"${COMPOSE[@]}" exec -T db pg_restore --list < "$TARGET/db.dump" >/dev/null

echo "Backing up uploads..." >&2
"${COMPOSE[@]}" exec -T backend tar -czf - -C /app/backend/uploads . \
  > "$TARGET/uploads.tar.gz"
tar -tzf "$TARGET/uploads.tar.gz" >/dev/null

for table in user gym athlete_profile body_analysis_file workout_program_version; do
  "${COMPOSE[@]}" exec -T db psql -U postgres -d "$POSTGRES_DB" -Atc \
    "SELECT count(*) FROM \"$table\";" >> "$TARGET/counts.txt"
done
finance_schema="$("${COMPOSE[@]}" exec -T db psql -U postgres -d "$POSTGRES_DB" -Atc \
  "SELECT to_regclass('public.finance_journal_line');")"
if [ -n "$finance_schema" ]; then
  for table in finance_settings finance_audit finance_account finance_period \
    finance_sequence finance_journal finance_journal_line finance_grant \
    finance_operation finance_catalog_item finance_invoice \
    finance_invoice_line finance_installment finance_receipt \
    finance_receipt_allocation finance_customer_credit \
    finance_credit_movement finance_refund finance_expense finance_membership \
    finance_coach_agreement finance_coach_agreement_term \
    finance_coach_earning finance_coach_settlement \
    finance_coach_settlement_item finance_coach_earning_adjustment \
    finance_coach_discrepancy finance_bank_statement_line; do
    "${COMPOSE[@]}" exec -T db psql -U postgres -d "$POSTGRES_DB" -Atc \
      "SELECT count(*) FROM \"$table\";" >> "$TARGET/finance-counts.txt"
  done
fi
platform_schema="$("${COMPOSE[@]}" exec -T db psql -U postgres -d "$POSTGRES_DB" -Atc \
  "SELECT to_regclass('public.platform_sequence');")"
if [ -n "$platform_schema" ]; then
  for table in platform_plan platform_plan_version platform_group \
    platform_group_member platform_agreement platform_commission_term \
    platform_receivable platform_credit platform_credit_application \
    platform_invoice platform_invoice_line platform_invoice_cancellation \
    platform_invoice_line_reversal platform_payment \
    platform_payment_allocation platform_journal platform_journal_line \
    platform_audit platform_cost platform_operation platform_sequence; do
    "${COMPOSE[@]}" exec -T db psql -U postgres -d "$POSTGRES_DB" -Atc \
      "SELECT count(*) FROM \"$table\";" >> "$TARGET/platform-counts.txt"
  done
fi

sha() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}
{
  printf '%s  %s\n' "$(sha "$TARGET/db.dump")" "db.dump"
  printf '%s  %s\n' "$(sha "$TARGET/uploads.tar.gz")" "uploads.tar.gz"
  printf '%s  %s\n' "$(sha "$TARGET/counts.txt")" "counts.txt"
  if [ -f "$TARGET/finance-counts.txt" ]; then
    printf '%s  %s\n' "$(sha "$TARGET/finance-counts.txt")" "finance-counts.txt"
  fi
  if [ -f "$TARGET/platform-counts.txt" ]; then
    printf '%s  %s\n' "$(sha "$TARGET/platform-counts.txt")" "platform-counts.txt"
  fi
} > "$TARGET/checksums.txt"

chmod 600 "$TARGET"/*
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/last_success"
chmod 600 "$BACKUP_DIR/last_success"

if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
  command -v rclone >/dev/null 2>&1 || {
    echo "rclone is required for BACKUP_RCLONE_REMOTE" >&2
    exit 1
  }
  rclone copy "$TARGET" "$BACKUP_RCLONE_REMOTE"
fi

if [ "$RETENTION_DAYS" -gt 0 ] 2>/dev/null; then
  find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" \
    -exec rm -rf {} +
fi

echo "backup_path=$TARGET"
