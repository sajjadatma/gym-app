import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  BellRing,
  BookOpen,
  CalendarClock,
  Lock,
  Plus,
  ShieldCheck,
  Trash2,
  Wallet,
} from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type FinanceGrantItem,
  type FinanceJournalPublic,
  FinanceService,
  GymsService,
  type MemberPublic,
} from "@/client"
import { DateField } from "@/components/DateField"
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  SectionCard,
  SelectField,
  Spinner,
  Switch,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { formatIrr, parseAmountInUnit, parseIrrInput } from "@/lib/money"
import { useSnackbar } from "@/snackbar"
import type { FinanceSectionProps } from "./shared"

type OpeningLine = {
  key: string
  accountCode: string
  side: "debit" | "credit"
  amount: string
}

const DEFAULT_LINES: OpeningLine[] = [
  { key: "debit", accountCode: "1000", side: "debit", amount: "" },
  { key: "credit", accountCode: "3000", side: "credit", amount: "" },
]

const GRANT_PERMISSIONS = [
  { permission: "finance.opening.manage", label: "finance.grantOpening" },
  { permission: "finance.period.manage", label: "finance.grantPeriod" },
  { permission: "finance.catalog.manage", label: "finance.grantCatalog" },
  { permission: "finance.invoice.manage", label: "finance.grantInvoice" },
  { permission: "finance.payment.record", label: "finance.grantPayment" },
  { permission: "finance.refund.manage", label: "finance.grantRefund" },
  { permission: "finance.expense.manage", label: "finance.grantExpense" },
  { permission: "finance.membership.manage", label: "finance.grantMembership" },
  {
    permission: "finance.coach_agreement.manage",
    label: "finance.grantCoachAgreement",
  },
  { permission: "finance.settlement.manage", label: "finance.grantSettlement" },
] as const

function newKey() {
  return `line-${Math.random().toString(36).slice(2, 9)}`
}

function todayIso() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export function FinanceOverviewSection({
  settings,
  unit,
}: FinanceSectionProps) {
  const { t, formatNumber, formatDate, normalizeDigits } = useI18n()
  const unitLabel = t(
    unit === "RIAL" ? "finance.unitRial" : "finance.unitToman",
  )
  const { activeGymId, isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()

  const [openingOpen, setOpeningOpen] = useState(false)
  const [openingKey, setOpeningKey] = useState(newKey)
  const [postingDate, setPostingDate] = useState(todayIso)
  const [openingDescription, setOpeningDescription] = useState("")
  const [lines, setLines] = useState<OpeningLine[]>(DEFAULT_LINES)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [correcting, setCorrecting] = useState<FinanceJournalPublic | null>(
    null,
  )
  const [correctionReason, setCorrectionReason] = useState("")
  const [grantTarget, setGrantTarget] = useState<MemberPublic | null>(null)
  const [grantSelected, setGrantSelected] = useState<Record<string, boolean>>(
    {},
  )
  const [grantLimit, setGrantLimit] = useState("")

  const scope = activeGymId ?? ""
  const accountsQuery = useQuery({
    queryKey: ["finance", scope, "accounts"],
    queryFn: async () => (await FinanceService.listFinanceAccounts()).data,
    enabled: Boolean(activeGymId),
  })
  const journalQuery = useQuery({
    queryKey: ["finance", scope, "journal"],
    queryFn: async () =>
      (await FinanceService.readFinanceJournal({ query: { limit: 50 } })).data,
    enabled: Boolean(activeGymId),
  })
  const periodsQuery = useQuery({
    queryKey: ["finance", scope, "periods"],
    queryFn: async () => (await FinanceService.readFinancePeriods()).data,
    enabled: Boolean(activeGymId),
  })
  const membersQuery = useQuery({
    queryKey: ["finance", scope, "members"],
    queryFn: async () =>
      (
        await GymsService.listMembers({
          path: { gym_id: activeGymId! },
          query: { staff_only: true, offset: 0, limit: 50 },
        })
      ).data,
    enabled: Boolean(activeGymId && isAdmin),
  })
  const grantsQuery = useQuery({
    queryKey: ["finance", scope, "grants"],
    queryFn: async () => (await FinanceService.readFinanceGrants()).data,
    enabled: Boolean(activeGymId && isAdmin),
  })
  const [horizon, setHorizon] = useState(7)
  const remindersQuery = useQuery({
    queryKey: ["finance", scope, "reminders", horizon],
    queryFn: async () =>
      (
        await FinanceService.readFinanceReminders({
          query: { within_days: horizon },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })

  const accounts = accountsQuery.data?.data ?? []
  const entries = journalQuery.data?.data ?? []
  const periods = periodsQuery.data?.data ?? []
  const entryNumbers = new Map(
    entries.map((entry) => [entry.id, entry.entry_number]),
  )
  const reversedIds = new Set(
    entries
      .filter((entry) => entry.reversal_of_id)
      .map((entry) => entry.reversal_of_id as string),
  )
  // The latest opening balance that has not been reversed is the active one;
  // a superuser may restate it by reversing and posting a corrected opening.
  const openingEntry = entries.find(
    (entry) =>
      entry.event_type === "OPENING_BALANCE" && !reversedIds.has(entry.id),
  )
  const hadOpening = entries.some(
    (entry) => entry.event_type === "OPENING_BALANCE",
  )
  const canPost =
    settings.enabled &&
    settings.permissions.includes("finance.opening.manage") &&
    !openingEntry &&
    !journalQuery.isLoading &&
    !journalQuery.isError
  const canClose =
    settings.enabled && settings.permissions.includes("finance.period.manage")
  const openPeriod = periods.find((period) => period.status === "OPEN")
  const money = (amount: number) => formatIrr(amount, unit, formatNumber)

  const accountOptions = accounts.map((account) => ({
    value: account.code,
    label: `${account.code} · ${account.name}`,
  }))
  const financeStaff = (membersQuery.data?.data ?? []).filter((member) =>
    member.roles.includes("FINANCE_STAFF"),
  )
  const grantsByUser = new Map(
    (grantsQuery.data?.data ?? []).map((row) => [row.user_id, row.grants]),
  )

  function invalidate() {
    return queryClient.invalidateQueries({
      queryKey: ["finance", scope],
    })
  }

  async function updateSettings(patch: {
    enabled?: boolean
    display_unit?: "RIAL" | "TOMAN"
  }) {
    setSaving(true)
    try {
      await FinanceService.updateFinanceSettings({ body: patch })
      await invalidate()
      show(t("common.saved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  function resetOpening() {
    setOpeningKey(newKey())
    setPostingDate(todayIso())
    setOpeningDescription("")
    setLines(DEFAULT_LINES.map((line) => ({ ...line })))
    setFormError(null)
  }

  function updateLine(key: string, patch: Partial<OpeningLine>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )
  }

  function openingTotal(side: "debit" | "credit") {
    return lines.reduce((total, line) => {
      if (line.side !== side) return total
      return total + (parseAmountInUnit(line.amount || "0", unit) ?? 0)
    }, 0)
  }

  async function submitOpening() {
    setFormError(null)
    const parsed = lines.map((line) => ({
      line,
      irr: parseAmountInUnit(line.amount, unit),
    }))
    if (parsed.some((item) => item.irr === null || item.irr <= 0)) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    const debit = openingTotal("debit")
    const credit = openingTotal("credit")
    if (debit !== credit || debit === 0) {
      setFormError(t("finance.unbalanced"))
      return
    }
    setSaving(true)
    try {
      await FinanceService.postFinanceOpeningBalance({
        body: {
          posting_date: postingDate,
          description: openingDescription || null,
          lines: parsed.map(({ line, irr }) => ({
            account_code: line.accountCode,
            debit_irr: line.side === "debit" ? (irr as number) : 0,
            credit_irr: line.side === "credit" ? (irr as number) : 0,
          })),
        },
        headers: { "Idempotency-Key": openingKey },
      })
      await invalidate()
      setOpeningOpen(false)
      resetOpening()
      show(t("finance.posted"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function submitCorrection() {
    if (!correcting) return
    if (correctionReason.trim().length < 3) return
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.correctFinanceJournal({
        path: { journal_id: correcting.id },
        body: { reason: correctionReason.trim(), posting_date: todayIso() },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setCorrecting(null)
      setCorrectionReason("")
      show(t("finance.corrected"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function closePeriod() {
    setSaving(true)
    try {
      await FinanceService.closeFinancePeriod()
      await invalidate()
      show(t("finance.periodClosed"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  function openGrantDialog(member: MemberPublic) {
    const grants = grantsByUser.get(member.user_id) ?? []
    setGrantTarget(member)
    setGrantSelected(
      Object.fromEntries(grants.map((item) => [item.permission, true])),
    )
    const opening = grants.find(
      (item) => item.permission === "finance.opening.manage",
    )
    setGrantLimit(
      opening?.amount_limit_irr != null ? String(opening.amount_limit_irr) : "",
    )
    setFormError(null)
  }

  async function saveGrants() {
    if (!grantTarget) return
    const grants: FinanceGrantItem[] = []
    for (const item of GRANT_PERMISSIONS) {
      if (!grantSelected[item.permission]) continue
      if (item.permission === "finance.opening.manage") {
        const limit = grantLimit.trim() ? parseIrrInput(grantLimit) : null
        if (grantLimit.trim() && limit === null) {
          setFormError(t("finance.invalidAmount"))
          return
        }
        grants.push({
          permission: "finance.opening.manage",
          amount_limit_irr: limit,
        })
      } else {
        grants.push({
          permission: item.permission as FinanceGrantItem["permission"],
        })
      }
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.updateFinanceGrants({
        path: { user_id: grantTarget.user_id },
        body: { grants },
      })
      await invalidate()
      setGrantTarget(null)
      show(t("finance.grantsSaved"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <SectionCard
        title={t("finance.reminders")}
        subtitle={t("finance.remindersHint")}
        actions={
          <SelectField
            label={t("finance.reminderHorizon")}
            value={String(horizon)}
            onChange={(value) => setHorizon(Number(value))}
            options={[
              { value: "7", label: t("finance.days7") },
              { value: "30", label: t("finance.days30") },
              { value: "90", label: t("finance.days90") },
            ]}
          />
        }
      >
        {remindersQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : remindersQuery.isError ? (
          <ErrorState
            message={translateApiError(remindersQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => remindersQuery.refetch()}
          />
        ) : (remindersQuery.data?.installments.length ?? 0) === 0 &&
          (remindersQuery.data?.renewals.length ?? 0) === 0 ? (
          <EmptyState
            icon={<BellRing size={24} />}
            title={t("finance.remindersEmpty")}
          />
        ) : (
          <div className="stack">
            <h3 className="m3-section__subtitle">
              {t("finance.reminderInstallments")}
            </h3>
            {(remindersQuery.data?.installments.length ?? 0) === 0 ? (
              <p className="muted">{t("finance.remindersEmpty")}</p>
            ) : (
              remindersQuery.data?.installments.map((item) => (
                <div
                  key={`${item.invoice_id}-${item.due_date}`}
                  className="row row--between"
                >
                  <div>
                    <strong>{item.customer_name ?? "—"}</strong>
                    <div className="muted">
                      {t("finance.invoice.number")}{" "}
                      {item.invoice_number
                        ? formatNumber(item.invoice_number)
                        : "—"}{" "}
                      · {formatDate(item.due_date)}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 8 }}>
                    <span>{money(item.amount_irr)}</span>
                    <span
                      className="m3-chip"
                      style={
                        item.overdue ? { color: "var(--m3-error)" } : undefined
                      }
                    >
                      {item.overdue
                        ? t("finance.overdue")
                        : t("finance.dueInDays", {
                            days: formatNumber(item.days_until),
                          })}
                    </span>
                  </div>
                </div>
              ))
            )}
            <h3 className="m3-section__subtitle">
              {t("finance.reminderRenewals")}
            </h3>
            {(remindersQuery.data?.renewals.length ?? 0) === 0 ? (
              <p className="muted">{t("finance.remindersEmpty")}</p>
            ) : (
              remindersQuery.data?.renewals.map((item) => (
                <div key={item.membership_id} className="row row--between">
                  <div>
                    <strong>{item.athlete_name ?? "—"}</strong>
                    <div className="muted">{formatDate(item.end_date)}</div>
                  </div>
                  <span
                    className="m3-chip"
                    style={
                      item.overdue ? { color: "var(--m3-error)" } : undefined
                    }
                  >
                    {item.overdue
                      ? t("finance.overdue")
                      : t("finance.dueInDays", {
                          days: formatNumber(item.days_until),
                        })}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.settings")}
        subtitle={t("finance.enableHint")}
      >
        <div className="stack">
          {settings.can_toggle ? (
            <Switch
              label={t("finance.enableFinance")}
              checked={settings.enabled}
              disabled={saving}
              onChange={(checked) => void updateSettings({ enabled: checked })}
            />
          ) : null}
          <SelectField
            label={t("finance.displayUnit")}
            value={unit}
            disabled={!settings.can_manage || saving}
            onChange={(value) =>
              void updateSettings({ display_unit: value as "RIAL" | "TOMAN" })
            }
            options={[
              { value: "RIAL", label: t("finance.unitRial") },
              { value: "TOMAN", label: t("finance.unitToman") },
            ]}
          />
        </div>
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.openingBalance")}
        subtitle={t("finance.openingHint")}
        actions={
          canPost ? (
            <Button
              icon={<Plus size={16} />}
              onClick={() => {
                resetOpening()
                setOpeningOpen(true)
              }}
            >
              {t("finance.postOpening")}
            </Button>
          ) : null
        }
      >
        {openingEntry ? (
          <div className="stack">
            <p className="muted">
              {t("finance.openingPosted")}{" "}
              {t("finance.entry", {
                number: formatNumber(openingEntry.entry_number),
              })}
            </p>
            <div className="m3-entity-card__meta">
              {formatDate(openingEntry.posting_date)}
            </div>
          </div>
        ) : (
          <p className="muted">
            {hadOpening
              ? t("finance.openingReversed")
              : t("finance.journalEmptyHint")}
          </p>
        )}
        {accountsQuery.isError ? (
          <div className="m3-inline-alert" role="alert">
            {translateApiError(accountsQuery.error, t)}
          </div>
        ) : null}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.journal")}
        subtitle={t("finance.subtitle")}
      >
        {journalQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : journalQuery.isError ? (
          <ErrorState
            message={translateApiError(journalQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => journalQuery.refetch()}
          />
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<BookOpen size={24} />}
            title={t("finance.journalEmpty")}
            description={t("finance.journalEmptyHint")}
          />
        ) : (
          <div className="stack">
            {entries.map((entry) => (
              <Card key={entry.id} variant="outlined">
                <div className="row row--between" style={{ gap: 12 }}>
                  <div>
                    <strong>
                      {t("finance.entry", {
                        number: formatNumber(entry.entry_number),
                      })}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>{formatDate(entry.posting_date)}</span>
                      <span className="m3-chip">
                        {entry.event_type === "OPENING_BALANCE"
                          ? t("finance.opening")
                          : t("finance.correction")}
                      </span>
                      {entry.reversal_of_id &&
                      entryNumbers.has(entry.reversal_of_id) ? (
                        <span className="muted">
                          {t("finance.reverses", {
                            number: formatNumber(
                              entryNumbers.get(entry.reversal_of_id)!,
                            ),
                          })}
                        </span>
                      ) : null}
                    </div>
                    {entry.description ? (
                      <p className="muted">{entry.description}</p>
                    ) : null}
                  </div>
                  {entry.id === openingEntry?.id &&
                  settings.enabled &&
                  settings.can_toggle ? (
                    <Button
                      variant="text"
                      size="sm"
                      icon={<Lock size={15} />}
                      onClick={() => {
                        setCorrectionReason("")
                        setFormError(null)
                        setCorrecting(entry)
                      }}
                    >
                      {t("finance.correct")}
                    </Button>
                  ) : null}
                </div>
                <div className="m3-table-wrap">
                  <table className="m3-table">
                    <thead>
                      <tr>
                        <th>{t("finance.account")}</th>
                        <th>
                          {t("finance.debit")} ({unitLabel})
                        </th>
                        <th>
                          {t("finance.credit")} ({unitLabel})
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {entry.lines.map((line) => (
                        <tr key={line.id}>
                          <td>
                            {line.account_code} · {line.account_name}
                          </td>
                          <td>
                            {line.debit_irr ? money(line.debit_irr) : "—"}
                          </td>
                          <td>
                            {line.credit_irr ? money(line.credit_irr) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.periods")}
        subtitle={t("finance.periodNotice")}
        actions={
          canClose && openPeriod ? (
            <Button
              variant="tonal"
              icon={<CalendarClock size={16} />}
              loading={saving}
              onClick={() => void closePeriod()}
            >
              {t("finance.closePeriod")}
            </Button>
          ) : null
        }
      >
        {periodsQuery.isError ? (
          <ErrorState
            message={translateApiError(periodsQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => periodsQuery.refetch()}
          />
        ) : periods.length === 0 ? (
          <p className="muted">{t("finance.noPeriods")}</p>
        ) : (
          <div className="stack">
            {periods.map((period) => (
              <div key={period.id} className="row row--between">
                <span>{formatDate(period.opened_at)}</span>
                <span className="m3-chip">
                  {period.status === "OPEN"
                    ? t("finance.periodOpen")
                    : t("finance.periodClosed")}
                </span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {isAdmin ? (
        <>
          <div style={{ height: 16 }} />
          <SectionCard
            title={t("finance.grants")}
            subtitle={t("finance.grantsHint")}
          >
            {financeStaff.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck size={24} />}
                title={t("finance.noFinanceStaff")}
                description={t("finance.noFinanceStaffHint")}
              />
            ) : (
              <div className="stack">
                {financeStaff.map((member) => (
                  <div key={member.membership_id} className="row row--between">
                    <div>
                      <strong>{member.full_name ?? member.email}</strong>
                      <div className="muted" dir="ltr">
                        {member.email}
                      </div>
                    </div>
                    <Button
                      variant="text"
                      size="sm"
                      icon={<Wallet size={15} />}
                      onClick={() => openGrantDialog(member)}
                    >
                      {t("finance.manageAccess")}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>
        </>
      ) : null}

      <Dialog
        open={openingOpen}
        title={t("finance.postOpening")}
        description={t("finance.openingHint")}
        onClose={() => setOpeningOpen(false)}
        size="lg"
        footer={
          <>
            <Button variant="text" onClick={() => setOpeningOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void submitOpening()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {formError ? (
            <div className="m3-inline-alert" role="alert">
              {formError}
            </div>
          ) : null}
          <DateField
            label={t("finance.postingDate")}
            value={postingDate}
            onChange={(value) => setPostingDate(value ?? todayIso())}
            required
          />
          <TextField
            label={t("finance.description")}
            value={openingDescription}
            onChange={(event) => setOpeningDescription(event.target.value)}
          />
          {lines.map((line, index) => (
            <div key={line.key} className="stack">
              <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
                <SelectField
                  label={t("finance.account")}
                  value={line.accountCode}
                  onChange={(value) =>
                    updateLine(line.key, { accountCode: value })
                  }
                  options={accountOptions}
                  containerClassName="grow"
                />
                <SelectField
                  label={t("finance.amount")}
                  value={line.side}
                  onChange={(value) =>
                    updateLine(line.key, {
                      side: value as "debit" | "credit",
                    })
                  }
                  options={[
                    { value: "debit", label: t("finance.debit") },
                    { value: "credit", label: t("finance.credit") },
                  ]}
                />
                <TextField
                  label={t("finance.amountIn", { unit: unitLabel })}
                  value={line.amount}
                  inputMode="decimal"
                  dir="auto"
                  onChange={(event) =>
                    updateLine(line.key, {
                      amount: normalizeDigits(event.target.value),
                    })
                  }
                />
                {lines.length > 2 ? (
                  <Button
                    variant="text"
                    aria-label={t("finance.removeLine")}
                    icon={<Trash2 size={16} />}
                    onClick={() =>
                      setLines((current) =>
                        current.filter((item) => item.key !== line.key),
                      )
                    }
                  />
                ) : null}
              </div>
              {index === lines.length - 1 ? (
                <Button
                  variant="text"
                  size="sm"
                  icon={<Plus size={15} />}
                  onClick={() =>
                    setLines((current) => [
                      ...current,
                      {
                        key: newKey(),
                        accountCode: accounts[0]?.code ?? "1000",
                        side: "debit",
                        amount: "",
                      },
                    ])
                  }
                >
                  {t("finance.addLine")}
                </Button>
              ) : null}
            </div>
          ))}
          <div className="row row--between">
            <span>
              {t("finance.totalDebit")}: {money(openingTotal("debit"))}{" "}
              {unitLabel}
            </span>
            <span>
              {t("finance.totalCredit")}: {money(openingTotal("credit"))}{" "}
              {unitLabel}
            </span>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={correcting !== null}
        title={t("finance.correct")}
        description={t("finance.correctHint")}
        onClose={() => setCorrecting(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setCorrecting(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={correctionReason.trim().length < 3}
              onClick={() => void submitCorrection()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {formError ? (
            <div className="m3-inline-alert" role="alert">
              {formError}
            </div>
          ) : null}
          <TextField
            label={t("finance.correctReason")}
            value={correctionReason}
            onChange={(event) => setCorrectionReason(event.target.value)}
            multiline
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={grantTarget !== null}
        title={t("finance.manageAccess")}
        description={grantTarget?.full_name ?? grantTarget?.email}
        onClose={() => setGrantTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setGrantTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void saveGrants()}>
              {t("finance.saveGrants")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {formError ? (
            <div className="m3-inline-alert" role="alert">
              {formError}
            </div>
          ) : null}
          {GRANT_PERMISSIONS.map((item) => (
            <Switch
              key={item.permission}
              label={t(item.label)}
              checked={Boolean(grantSelected[item.permission])}
              onChange={(checked) =>
                setGrantSelected((current) => ({
                  ...current,
                  [item.permission]: checked,
                }))
              }
            />
          ))}
          {grantSelected["finance.opening.manage"] ? (
            <TextField
              label={t("finance.limit")}
              helper={t("finance.limitHint")}
              value={grantLimit}
              inputMode="numeric"
              dir="auto"
              onChange={(event) =>
                setGrantLimit(normalizeDigits(event.target.value))
              }
            />
          ) : null}
        </div>
      </Dialog>
    </>
  )
}
