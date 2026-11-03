#!/usr/bin/env bash
# Isolated restore drill against the disposable CI stack.
# Expects a freshly started stack; the fixed fixture rows are not rerunnable.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-gym-ci}"
export BACKEND_IMAGE="${BACKEND_IMAGE:-gym-app-ci:local}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ci-postgres-password}"
export SECRET_KEY="${SECRET_KEY:-ci-only-secret-key-not-for-production-0123456789}"
export FIRST_SUPERUSER="${FIRST_SUPERUSER:-ci-superuser@example.com}"
export FIRST_SUPERUSER_PASSWORD="${FIRST_SUPERUSER_PASSWORD:-ci-only-superuser-password}"
export DOMAIN="${DOMAIN:-localhost}"
export ACME_EMAIL="${ACME_EMAIL:-ci@example.com}"
export ACME_CA_SERVER="${ACME_CA_SERVER:-https://acme-staging-v02.api.letsencrypt.org/directory}"
export DEPLOY_ENV=ci
COMPOSE=(docker compose -f compose.deploy.yml -f compose.ci.yml)
NETWORK="${COMPOSE_PROJECT_NAME}_internal"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; "${COMPOSE[@]}" exec -T db psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS app_restore" >/dev/null 2>&1 || true' EXIT

athlete_id="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  'SELECT user_id FROM athlete_profile ORDER BY created_at LIMIT 1;')"
gym_id="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  "SELECT gym_id FROM athlete_profile WHERE user_id='$athlete_id';")"
[ -n "$athlete_id" ] && [ -n "$gym_id" ] || { echo "drill: FAIL no seeded athlete" >&2; exit 1; }

"${COMPOSE[@]}" exec -T backend sh -c \
  'printf drill-pdf-bytes > /app/backend/uploads/body-analysis/ci-drill.pdf'
"${COMPOSE[@]}" exec -T db psql -U postgres -d app -v ON_ERROR_STOP=1 -c \
  "INSERT INTO body_analysis_file (id,gym_id,athlete_user_id,uploaded_by_id,original_name,stored_name,content_type,size_bytes,created_at) VALUES (gen_random_uuid(),'$gym_id','$athlete_id',NULL,'ci-drill.pdf','ci-drill.pdf','application/pdf',15,now());"

# A posted, balanced finance journal must survive the backup and restore.
finance_gym="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  "SELECT g.id FROM gym g WHERE NOT EXISTS (
     SELECT 1 FROM finance_journal j
     WHERE j.gym_id = g.id AND j.event_type = 'OPENING_BALANCE')
   ORDER BY g.created_at LIMIT 1;")"
[ -n "$finance_gym" ] || { echo "drill: FAIL no gym without an opening journal" >&2; exit 1; }
"${COMPOSE[@]}" exec -T db psql -U postgres -d app -v ON_ERROR_STOP=1 <<SQL
WITH period AS (
  INSERT INTO finance_period (id, gym_id, opened_at, created_at)
  VALUES (gen_random_uuid(), '$finance_gym', now(), now())
  RETURNING id
), journal AS (
  INSERT INTO finance_journal
    (id, gym_id, period_id, entry_number, posting_date, event_type,
     description, created_at)
  SELECT gen_random_uuid(), '$finance_gym', id, 1, current_date,
         'OPENING_BALANCE', 'ci-drill', now()
  FROM period
  RETURNING id, gym_id
)
INSERT INTO finance_journal_line
  (id, journal_id, account_id, debit_irr, credit_irr, memo)
SELECT gen_random_uuid(), journal.id, account.id,
       CASE WHEN account.code = '1000' THEN 1000 ELSE 0 END,
       CASE WHEN account.code = '3000' THEN 1000 ELSE 0 END,
       'ci-drill'
FROM journal
JOIN finance_account account
  ON account.gym_id = journal.gym_id AND account.code IN ('1000', '3000');
INSERT INTO finance_sequence (id, gym_id, doc_type, last_value)
VALUES (gen_random_uuid(), '$finance_gym', 'JOURNAL', 1)
ON CONFLICT (gym_id, doc_type) DO UPDATE
  SET last_value = GREATEST(finance_sequence.last_value, 1);
SQL


PLATFORM_RECEIVABLE_ID="00000000-0000-0000-0000-000000000101"
PLATFORM_INVOICE_ID="00000000-0000-0000-0000-000000000102"
PLATFORM_LINE_ID="00000000-0000-0000-0000-000000000103"
PLATFORM_PAYMENT_ID="00000000-0000-0000-0000-000000000104"
PLATFORM_JOURNAL_ID="00000000-0000-0000-0000-000000000105"
PLATFORM_AGREEMENT_ID="00000000-0000-0000-0000-000000000106"
"${COMPOSE[@]}" exec -T db psql -U postgres -d app -v ON_ERROR_STOP=1 <<SQL
BEGIN;
INSERT INTO platform_agreement
  (id, gym_id, group_id, version, supersedes_id, mode, status,
   effective_from, effective_to, plan_version_id, subscription_amount_irr,
   billing_interval, volume_discount_bp, grace_days, restrict_after_days,
   created_by_id, created_at, activated_at)
VALUES
  ('$PLATFORM_AGREEMENT_ID', '$finance_gym', NULL, 1, NULL, 'COMMISSION',
   'EFFECTIVE', current_date, NULL, NULL, 0, 'MONTHLY', 0, 7, 21,
   NULL, now(), now());
INSERT INTO platform_receivable
  (id, gym_id, agreement_id, source_type, source_id, source_key, amount_irr,
   paid_irr, due_on, status, snapshot, created_at)
VALUES
  ('$PLATFORM_RECEIVABLE_ID', '$finance_gym', '$PLATFORM_AGREEMENT_ID',
   'COMMISSION', NULL, 'ci-drill-platform', 5000, 2500, current_date,
   'PARTIAL', '{}', now());
INSERT INTO platform_invoice
  (id, gym_id, group_id, invoice_number, period_start, period_end, issued_on,
   due_on, status, discount_irr, total_irr, created_by_id, created_at)
VALUES
  ('$PLATFORM_INVOICE_ID', '$finance_gym', NULL, 1, current_date, current_date,
   current_date, current_date, 'PARTIALLY_PAID', 0, 4500, NULL, now());
INSERT INTO platform_invoice_line
  (id, invoice_id, gym_id, receivable_id, source_key, description, gross_irr,
   discount_irr, credit_irr, amount_irr, paid_irr)
VALUES
  ('$PLATFORM_LINE_ID', '$PLATFORM_INVOICE_ID', '$finance_gym',
   '$PLATFORM_RECEIVABLE_ID', 'ci-drill-platform', 'ci drill', 5000, 0, 500,
   4500, 2000);
INSERT INTO platform_payment
  (id, invoice_id, amount_irr, method, reference, received_on, operation_key,
   created_by_id, created_at)
VALUES
  ('$PLATFORM_PAYMENT_ID', '$PLATFORM_INVOICE_ID', 2000, 'CASH', 'CI-DRILL',
   current_date, 'ci-drill-payment', NULL, now());
INSERT INTO platform_payment_allocation
  (id, payment_id, invoice_line_id, amount_irr)
VALUES
  (gen_random_uuid(), '$PLATFORM_PAYMENT_ID', '$PLATFORM_LINE_ID', 2000);
INSERT INTO platform_credit
  (id, gym_id, source_type, source_id, source_key, amount_irr, reason,
   created_by_id, created_at)
VALUES
  (gen_random_uuid(), '$finance_gym', 'MANUAL', NULL, 'ci-drill-credit', 500,
   'ci drill', NULL, now());
INSERT INTO platform_credit_application
  (id, credit_id, invoice_line_id, amount_irr, created_at)
SELECT gen_random_uuid(), id, '$PLATFORM_LINE_ID', 500, now()
FROM platform_credit WHERE source_key = 'ci-drill-credit';
INSERT INTO platform_journal
  (id, entry_number, posting_date, event_type, description, source_type,
   source_id, created_by_id, created_at)
VALUES
  ('$PLATFORM_JOURNAL_ID', 1, current_date, 'PLATFORM_FEE', 'ci drill',
   'platform_receivable', '$PLATFORM_RECEIVABLE_ID', NULL, now());
INSERT INTO platform_journal_line
  (id, journal_id, account_code, debit_irr, credit_irr, memo)
VALUES
  (gen_random_uuid(), '$PLATFORM_JOURNAL_ID', '1100', 5000, 0, 'ci drill'),
  (gen_random_uuid(), '$PLATFORM_JOURNAL_ID', '4100', 0, 5000, 'ci drill');
INSERT INTO platform_sequence (id, doc_type, last_value)
VALUES (gen_random_uuid(), 'PLATFORM_INVOICE', 1)
ON CONFLICT (doc_type) DO UPDATE
  SET last_value = GREATEST(platform_sequence.last_value, 1);
INSERT INTO platform_sequence (id, doc_type, last_value)
VALUES (gen_random_uuid(), 'PLATFORM_JOURNAL', 1)
ON CONFLICT (doc_type) DO UPDATE
  SET last_value = GREATEST(platform_sequence.last_value, 1);
COMMIT;
SQL

output="$(BACKUP_DIR="$TMP/backups" bash scripts/backup_compose.sh)"
backup_path="${output#backup_path=}"
[ -d "$backup_path" ] || { echo "drill: FAIL backup was not produced" >&2; exit 1; }
(cd "$backup_path" && shasum -a 256 -c checksums.txt)

"${COMPOSE[@]}" exec -T db psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -c 'CREATE DATABASE app_restore'
docker run --rm --network "$NETWORK" -e PGPASSWORD="$POSTGRES_PASSWORD" \
  -v "$backup_path:/backup:ro" postgres:17 \
  pg_restore --clean --if-exists --no-owner --no-privileges \
  -U postgres -d postgresql://postgres@db:5432/app_restore /backup/db.dump

mkdir -p "$TMP/restored-uploads"
tar -xzf "$backup_path/uploads.tar.gz" -C "$TMP/restored-uploads"
docker run --rm --network "$NETWORK" \
  -v "$ROOT/scripts/verify_restore.py:/verify_restore.py:ro" \
  -v "$TMP/restored-uploads/body-analysis:/uploads:ro" \
  -v "$backup_path/counts.txt:/counts.txt:ro" \
  -v "$backup_path/platform-counts.txt:/platform-counts.txt:ro" \
  "$BACKEND_IMAGE" python /verify_restore.py \
  --database-url "postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/app_restore" \
  --upload-dir /uploads --expected-counts /counts.txt \
  --expected-platform-counts /platform-counts.txt

restored_journals="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app_restore -Atc \
  'SELECT count(*) FROM finance_journal;')"
[ "$restored_journals" = "1" ] || {
  echo "drill: FAIL restored finance journals: $restored_journals" >&2
  exit 1
}
restored_unbalanced="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app_restore -Atc \
  'SELECT count(*) FROM (SELECT journal_id FROM finance_journal_line
     GROUP BY journal_id HAVING sum(debit_irr) <> sum(credit_irr)) AS bad;')"
[ "$restored_unbalanced" = "0" ] || {
  echo "drill: FAIL restored journals are unbalanced: $restored_unbalanced" >&2
  exit 1
}

assert_restored_count() {
  local table="$1" expected="$2" actual
  actual="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app_restore -Atc \
    "SELECT count(*) FROM $table;")"
  [ "$actual" = "$expected" ] || {
    echo "drill: FAIL restored $table: $actual (expected $expected)" >&2
    exit 1
  }
}
assert_restored_count platform_agreement 1
assert_restored_count platform_receivable 1
assert_restored_count platform_credit 1
assert_restored_count platform_credit_application 1
assert_restored_count platform_invoice 1
assert_restored_count platform_invoice_line 1
assert_restored_count platform_payment 1
assert_restored_count platform_payment_allocation 1
assert_restored_count platform_journal 1
assert_restored_count platform_journal_line 2
assert_restored_count platform_sequence 2

echo "drill: live restore through restore_compose.sh"
victim="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  'SELECT id FROM gym ORDER BY created_at LIMIT 1;')"
original="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  "SELECT name FROM gym WHERE id='$victim';")"
"${COMPOSE[@]}" exec -T db psql -U postgres -d app -v ON_ERROR_STOP=1 -c \
  "UPDATE gym SET name='CORRUPTED-BY-DRILL' WHERE id='$victim';"
BACKUP_PATH="$backup_path" DEPLOY_ENV=ci CONFIRM_RESTORE=YES \
  bash scripts/restore_compose.sh
restored="$("${COMPOSE[@]}" exec -T db psql -U postgres -d app -Atc \
  "SELECT name FROM gym WHERE id='$victim';")"
if [ "$restored" != "$original" ]; then
  echo "drill: FAIL live restore did not revert gym name" >&2
  exit 1
fi
curl -fsS http://localhost:8000/api/v1/utils/ready/ >/dev/null
echo "drill: live restore OK"

echo "drill: PASS"
