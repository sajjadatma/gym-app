import { useQuery, useQueryClient } from "@tanstack/react-query"
import { HandCoins, Plus, Sparkles } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionCard,
  SelectField,
  Spinner,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import {
  autoSettle,
  cancelSettlement,
  completeSettlement,
  createSettlement,
  getReport,
  listGymCoaches,
  listSettlements,
  type SettlementParty,
} from "@/lib/finance-api"
import {
  formatToman,
  parseTomanToIrr,
  partyLabel,
  statusLabel,
  todayIso,
} from "@/lib/finance-ui"
import { parseErrorMessage } from "@/lib/finance-validation"
import { useSnackbar } from "@/snackbar"

export function FinanceSettlementsPage({ gymId }: { gymId: string }) {
  const { t, formatNumber, formatDate } = useI18n()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [amountError, setAmountError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    party: "COACH" as SettlementParty,
    coachId: "",
    amountToman: "",
  })
  const settlements = useQuery({
    queryKey: ["finance-settlements", gymId],
    queryFn: () => listSettlements(gymId),
  })
  const coaches = useQuery({
    queryKey: ["finance-coaches", gymId, "with-balance"],
    queryFn: () => listGymCoaches(gymId, { withBalance: true }),
  })
  const report = useQuery({
    queryKey: ["finance-report-settlements", gymId],
    queryFn: () =>
      getReport({
        gym_id: gymId,
        from_date: todayIso(),
        to_date: todayIso(),
      }),
  })

  async function refresh() {
    await queryClient.invalidateQueries({
      queryKey: ["finance-settlements", gymId],
    })
    await queryClient.invalidateQueries({
      queryKey: ["finance-report-settlements", gymId],
    })
    await queryClient.invalidateQueries({ queryKey: ["finance-overview"] })
  }

  async function submit() {
    const parsed = parseTomanToIrr(form.amountToman)
    if (!parsed.ok || parsed.value <= 0) {
      setAmountError(
        parsed.ok
          ? t("finance.settlements.errorAmount")
          : (parseErrorMessage(parsed, "amount", t) ?? null),
      )
      return
    }
    if (form.party === "COACH" && !form.coachId) {
      setError(t("finance.settlements.errorCoach"))
      return
    }
    setSaving(true)
    setError(null)
    setAmountError(null)
    try {
      await createSettlement(gymId, {
        party: form.party,
        party_user_id: form.party === "COACH" ? form.coachId : null,
        amount_irr: parsed.value,
        idempotency_key: crypto.randomUUID(),
      })
      setOpen(false)
      await refresh()
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function complete(id: string) {
    setError(null)
    try {
      await completeSettlement(gymId, id)
      await refresh()
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    }
  }

  async function cancel(id: string) {
    setError(null)
    try {
      await cancelSettlement(gymId, id)
      await refresh()
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    }
  }

  async function runAuto() {
    setError(null)
    setSaving(true)
    try {
      await autoSettle(gymId)
      await refresh()
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  if (settlements.isLoading) return <Spinner label={t("common.loading")} />
  if (settlements.isError) {
    return (
      <ErrorState
        message={translateApiError(settlements.error, t)}
        onRetry={() => void settlements.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }
  const asOf = report.data?.as_of
  const available =
    form.party === "PLATFORM"
      ? asOf?.unsettled_platform_irr
      : form.party === "GYM"
        ? asOf?.unsettled_gym_irr
        : asOf?.unsettled_coach_irr

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={t("finance.settlements.title")}
        subtitle={t("finance.settlements.subtitle")}
        actions={
          <>
            <Button
              variant="outlined"
              icon={<Sparkles size={16} />}
              onClick={() => void runAuto()}
              loading={saving}
            >
              {t("finance.settlements.auto")}
            </Button>
            <Button
              icon={<Plus size={17} />}
              onClick={() => {
                setAmountError(null)
                setOpen(true)
              }}
            >
              {t("finance.settlements.new")}
            </Button>
          </>
        }
      />
      <div className="m3-finance-note">
        <HandCoins size={18} aria-hidden />
        <span>{t("finance.settlements.note")}</span>
      </div>
      {error ? <ErrorState message={error} /> : null}
      {settlements.data?.length === 0 ? (
        <EmptyState
          icon={<HandCoins size={24} />}
          title={t("finance.settlements.empty")}
          description={t("finance.settlements.emptyHint")}
          action={
            <Button
              icon={<Plus size={17} />}
              onClick={() => {
                setAmountError(null)
                setOpen(true)
              }}
            >
              {t("finance.settlements.new")}
            </Button>
          }
        />
      ) : (
        <SectionCard title={t("finance.settlements.listTitle")}>
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("finance.table.party")}</th>
                  <th>{t("finance.table.amount")}</th>
                  <th>{t("finance.table.status")}</th>
                  <th>{t("finance.table.requestedAt")}</th>
                  <th>{t("finance.table.completedAt")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {settlements.data?.map((row) => (
                  <tr key={row.id}>
                    <td>{row.party_name ?? partyLabel(row.party)}</td>
                    <td>{formatToman(row.amount_irr, formatNumber)}</td>
                    <td>
                      <span
                        className={`m3-status m3-status--${row.status.toLowerCase()}`}
                      >
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td>{formatDate(row.requested_at)}</td>
                    <td>
                      {row.completed_at ? formatDate(row.completed_at) : "—"}
                    </td>
                    <td>
                      <div className="m3-inline-actions">
                        {row.status === "PENDING" ? (
                          <>
                            <Button
                              size="sm"
                              variant="tonal"
                              onClick={() => void complete(row.id)}
                            >
                              {t("finance.settlements.complete")}
                            </Button>
                            <Button
                              size="sm"
                              variant="text"
                              onClick={() => void cancel(row.id)}
                            >
                              {t("common.cancel")}
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <Dialog
        open={open}
        title={t("finance.settlements.dialogTitle")}
        description={t("finance.settlements.dialogDescription")}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button
              variant="text"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void submit()} loading={saving}>
              {t("finance.settlements.create")}
            </Button>
          </>
        }
      >
        <div className="m3-form-grid">
          <SelectField
            label={t("finance.table.party")}
            value={form.party}
            onChange={(value) => {
              setForm((prev) => ({
                ...prev,
                party: value as SettlementParty,
              }))
              setError(null)
            }}
            options={[
              { value: "COACH", label: partyLabel("COACH") },
              { value: "GYM", label: partyLabel("GYM") },
              { value: "PLATFORM", label: partyLabel("PLATFORM") },
            ]}
          />
          {form.party === "COACH" ? (
            <SelectField
              label={t("finance.table.coach")}
              value={form.coachId}
              onChange={(value) =>
                setForm((prev) => ({ ...prev, coachId: value }))
              }
              options={(coaches.data ?? []).map((coach) => ({
                value: coach.user_id,
                label: coach.is_active
                  ? coach.name
                  : `${coach.name} — ${t("finance.settlements.departedCoach")}`,
              }))}
              required
            />
          ) : null}
          <TextField
            label={t("finance.settlements.amountToman")}
            value={form.amountToman}
            onChange={(event) => {
              setForm((prev) => ({
                ...prev,
                amountToman: event.target.value,
              }))
              setAmountError(null)
            }}
            inputMode="numeric"
            suffix={t("finance.unit.toman")}
            error={amountError ?? undefined}
            helper={
              available !== undefined
                ? `${t("finance.settlements.available")}: ${formatToman(available, formatNumber)}`
                : undefined
            }
            required
          />
        </div>
        <p className="m3-field__message">
          {t("finance.settlements.pendingHint")}
        </p>
        {error ? <ErrorState message={error} /> : null}
      </Dialog>
    </div>
  )
}
