import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Handshake, Plus, ShieldCheck, Trash2 } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type FinanceCoachAgreementPublic,
  type FinanceCoachEarningPublic,
  FinanceService,
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
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"
import {
  type FinanceSectionProps,
  methodLabel,
  newKey,
  todayIso,
  useFinanceCustomers,
  useMoney,
} from "./shared"

type PaymentMethod = "CASH" | "POS" | "TRANSFER"

type TermRow = {
  key: string
  recipient: "COACH" | "ASCORA" | "GYM"
  basis: "PERCENT" | "FIXED"
  value: string
}

function termRow(recipient: TermRow["recipient"], value: string): TermRow {
  return { key: newKey(), recipient, basis: "PERCENT", value }
}

export function FinanceCoachesSection({ settings, unit }: FinanceSectionProps) {
  const { t, formatDate, formatNumber, normalizeDigits } = useI18n()
  const { activeGymId, isSuperuser } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, parse, unitLabel } = useMoney(unit)
  const { coachOptions, customerName } = useFinanceCustomers()
  const canAgree = settings.permissions.includes(
    "finance.coach_agreement.manage",
  )
  const canSettle = settings.permissions.includes("finance.settlement.manage")
  const scope = activeGymId ?? ""

  const [agreementOpen, setAgreementOpen] = useState(false)
  const [coachId, setCoachId] = useState("")
  const [effectiveFrom, setEffectiveFrom] = useState(todayIso)
  const [effectiveTo, setEffectiveTo] = useState<string | null>(null)
  const [mode, setMode] = useState("DIRECT")
  const [vestingMode, setVestingMode] = useState("MANUAL")
  const [vestingDays, setVestingDays] = useState("0")
  const [periodicFixed, setPeriodicFixed] = useState("")
  const [periodicInterval, setPeriodicInterval] = useState("NONE")
  const [terms, setTerms] = useState<TermRow[]>([
    termRow("COACH", "30"),
    termRow("GYM", "70"),
  ])
  const [activateNow, setActivateNow] = useState(true)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [settlementOpen, setSettlementOpen] = useState(false)
  const [settleCoachId, setSettleCoachId] = useState("")
  const [settleAmount, setSettleAmount] = useState("")
  const [settleMethod, setSettleMethod] = useState<PaymentMethod>("CASH")
  const [settleReference, setSettleReference] = useState("")
  const [settleDate, setSettleDate] = useState(todayIso)

  const [vestTarget, setVestTarget] =
    useState<FinanceCoachEarningPublic | null>(null)
  const [vestReason, setVestReason] = useState("")
  const [resolveTarget, setResolveTarget] = useState<{
    id: string
    amount_irr: number
  } | null>(null)
  const [resolveNote, setResolveNote] = useState("")
  const [earningResolveTarget, setEarningResolveTarget] =
    useState<FinanceCoachEarningPublic | null>(null)
  const [earningAgreementId, setEarningAgreementId] = useState("")
  const [earningResolveReason, setEarningResolveReason] = useState("")
  const [periodicTarget, setPeriodicTarget] =
    useState<FinanceCoachAgreementPublic | null>(null)
  const [cancelTarget, setCancelTarget] = useState<{
    id: string
    amount_irr: number
  } | null>(null)
  const [cancelReason, setCancelReason] = useState("")
  const [period, setPeriod] = useState("")
  const [periodError, setPeriodError] = useState<string | null>(null)

  const agreementsQuery = useQuery({
    queryKey: ["finance", scope, "coach-agreements"],
    queryFn: async () => (await FinanceService.readCoachAgreements()).data,
    enabled: Boolean(activeGymId),
  })
  const earningsQuery = useQuery({
    queryKey: ["finance", scope, "coach-earnings"],
    queryFn: async () => (await FinanceService.readCoachEarnings()).data,
    enabled: Boolean(activeGymId),
  })
  const settlementsQuery = useQuery({
    queryKey: ["finance", scope, "coach-settlements"],
    queryFn: async () => (await FinanceService.readCoachSettlements()).data,
    enabled: Boolean(activeGymId),
  })
  const discrepanciesQuery = useQuery({
    queryKey: ["finance", scope, "coach-discrepancies"],
    queryFn: async () => (await FinanceService.readCoachDiscrepancies()).data,
    enabled: Boolean(activeGymId),
  })

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["finance", scope] })
  }

  function openAgreement() {
    setCoachId("")
    setEffectiveFrom(todayIso())
    setEffectiveTo(null)
    setMode("DIRECT")
    setVestingMode("MANUAL")
    setVestingDays("0")
    setPeriodicFixed("")
    setPeriodicInterval("NONE")
    setTerms([termRow("COACH", "30"), termRow("GYM", "70")])
    setActivateNow(true)
    setFormError(null)
    setAgreementOpen(true)
  }

  function updateTerm(key: string, patch: Partial<TermRow>) {
    setTerms((current) =>
      current.map((term) => (term.key === key ? { ...term, ...patch } : term)),
    )
  }

  function buildTerms() {
    const parsed = terms.map((term) => {
      if (term.basis === "PERCENT") {
        const percent = Number(normalizeDigits(term.value))
        if (!Number.isFinite(percent) || percent <= 0 || percent > 100) {
          return null
        }
        return {
          recipient: term.recipient,
          basis: term.basis,
          percent_bp: Math.round(percent * 100),
          fixed_irr: 0,
        }
      }
      const fixed = parse(term.value)
      if (fixed === null) return null
      return {
        recipient: term.recipient,
        basis: term.basis,
        percent_bp: 0,
        fixed_irr: fixed,
      }
    })
    return parsed.some((term) => term === null)
      ? null
      : (parsed as NonNullable<(typeof parsed)[number]>[])
  }

  async function createAgreement() {
    if (!coachId) {
      setFormError(t("finance.chooseCoach"))
      return
    }
    const parsedTerms = buildTerms()
    const periodicIrr = periodicFixed ? parse(periodicFixed) : 0
    if (periodicIrr === null) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    if (periodicInterval === "MONTHLY" && periodicIrr <= 0) {
      setFormError(t("finance.coaches.periodicAmountRequired"))
      return
    }
    if (!parsedTerms) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      const created = await FinanceService.createFinanceCoachAgreement({
        body: {
          coach_user_id: coachId,
          effective_from: effectiveFrom,
          effective_to: effectiveTo,
          mode: mode as "DIRECT" | "WATERFALL",
          vesting_mode: vestingMode as "ON_DATE" | "MANUAL",
          vesting_days: Number(normalizeDigits(vestingDays)) || 0,
          periodic_fixed_irr: periodicIrr,
          periodic_interval: periodicInterval as "NONE" | "MONTHLY",
          terms: parsedTerms,
        },
      })
      if (activateNow) {
        await FinanceService.activateFinanceCoachAgreement({
          path: { agreement_id: created.data.id },
        })
      }
      await invalidate()
      setAgreementOpen(false)
      show(t("finance.coaches.agreementCreated"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function activate(agreement: FinanceCoachAgreementPublic) {
    setSaving(true)
    try {
      await FinanceService.activateFinanceCoachAgreement({
        path: { agreement_id: agreement.id },
      })
      await invalidate()
      show(t("finance.coaches.agreementActivated"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function vest() {
    if (!vestTarget) return
    setSaving(true)
    try {
      await FinanceService.vestFinanceCoachEarning({
        path: { earning_id: vestTarget.id },
        body: { reason: vestReason.trim() },
      })
      await invalidate()
      setVestTarget(null)
      setVestReason("")
      show(t("finance.coaches.vested"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  function openSettlement() {
    setSettleCoachId("")
    setSettleAmount("")
    setSettleMethod("CASH")
    setSettleReference("")
    setSettleDate(todayIso())
    setFormError(null)
    setSettlementOpen(true)
  }

  async function settle() {
    if (!settleCoachId) {
      setFormError(t("finance.chooseCoach"))
      return
    }
    const amount = parse(settleAmount)
    if (amount === null || amount <= 0) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.createFinanceCoachSettlement({
        body: {
          coach_user_id: settleCoachId,
          amount_irr: amount,
          method: settleMethod,
          reference: settleReference.trim() || null,
          paid_on: settleDate,
          notes: null,
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setSettlementOpen(false)
      show(t("finance.coaches.settlementRecorded"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function cancelSettlement() {
    if (!cancelTarget) return
    setSaving(true)
    try {
      await FinanceService.cancelFinanceCoachSettlement({
        path: { settlement_id: cancelTarget.id },
        body: { reason: cancelReason.trim() },
      })
      await invalidate()
      setCancelTarget(null)
      setCancelReason("")
      show(t("finance.coaches.settlementCancelled"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function confirmSettlement(id: string) {
    setSaving(true)
    try {
      await FinanceService.confirmFinanceCoachSettlement({
        path: { settlement_id: id },
      })
      await invalidate()
      show(t("finance.coaches.settlementConfirmed"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function accruePeriod() {
    if (!periodicTarget) return
    setSaving(true)
    setPeriodError(null)
    try {
      await FinanceService.accrueFinanceCoachPeriod({
        path: { agreement_id: periodicTarget.id },
        body: { period: period.trim() },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setPeriodicTarget(null)
      setPeriod("")
      show(t("finance.coaches.periodAccrued"), "success")
    } catch (err) {
      setPeriodError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function resolveEarning() {
    if (!earningResolveTarget || !earningAgreementId) return
    setSaving(true)
    try {
      await FinanceService.resolveFinanceCoachEarning({
        path: { earning_id: earningResolveTarget.id },
        body: {
          agreement_id: earningAgreementId,
          reason: earningResolveReason.trim(),
        },
      })
      await invalidate()
      setEarningResolveTarget(null)
      setEarningAgreementId("")
      setEarningResolveReason("")
      show(t("finance.coaches.earningResolved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function resolveDiscrepancy() {
    if (!resolveTarget) return
    setSaving(true)
    try {
      await FinanceService.resolveFinanceCoachDiscrepancy({
        path: { discrepancy_id: resolveTarget.id },
        body: { resolution_note: resolveNote.trim() },
      })
      await invalidate()
      setResolveTarget(null)
      setResolveNote("")
      show(t("finance.coaches.discrepancyResolved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  const agreements = agreementsQuery.data?.data ?? []
  const earnings = earningsQuery.data?.data ?? []
  const settlements = settlementsQuery.data?.data ?? []
  const discrepancies = discrepanciesQuery.data?.data ?? []

  return (
    <>
      <SectionCard
        title={t("finance.coaches.agreements")}
        subtitle={t("finance.coaches.agreementsHint")}
        actions={
          canAgree ? (
            <Button icon={<Plus size={16} />} onClick={openAgreement}>
              {t("finance.coaches.newAgreement")}
            </Button>
          ) : null
        }
      >
        {agreementsQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : agreementsQuery.isError ? (
          <ErrorState
            message={translateApiError(agreementsQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => agreementsQuery.refetch()}
          />
        ) : agreements.length === 0 ? (
          <EmptyState
            icon={<Handshake size={24} />}
            title={t("finance.coaches.noAgreements")}
          />
        ) : (
          <div className="stack">
            {agreements.map((agreement) => (
              <Card key={agreement.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {agreement.coach_name ??
                        customerName(agreement.coach_user_id)}{" "}
                      · v{formatNumber(agreement.version)}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span className="m3-chip">{agreement.mode}</span>
                      <span className="m3-chip">{agreement.status}</span>
                      <span>
                        {formatDate(agreement.effective_from)}
                        {agreement.effective_to
                          ? ` — ${formatDate(agreement.effective_to)}`
                          : ""}
                      </span>
                      <span>{agreement.vesting_mode}</span>
                      {agreement.periodic_interval === "MONTHLY" ? (
                        <span>
                          {t("finance.coaches.periodic")}:{" "}
                          {money(agreement.periodic_fixed_irr ?? 0)}
                        </span>
                      ) : null}
                      <span>
                        {agreement.terms
                          .map(
                            (term) =>
                              `${term.recipient}: ${
                                term.basis === "PERCENT"
                                  ? `${formatNumber(term.percent_bp / 100)}%`
                                  : money(term.fixed_irr)
                              }`,
                          )
                          .join(" · ")}
                      </span>
                    </div>
                  </div>
                  {canAgree &&
                  agreement.status === "DRAFT" &&
                  (isSuperuser ||
                    !agreement.terms.some(
                      (term) => term.recipient === "ASCORA",
                    )) ? (
                    <Button
                      size="sm"
                      loading={saving}
                      onClick={() => void activate(agreement)}
                    >
                      {t("finance.coaches.activate")}
                    </Button>
                  ) : null}
                  {canAgree &&
                  agreement.status === "ACTIVE" &&
                  agreement.periodic_interval === "MONTHLY" &&
                  (agreement.periodic_fixed_irr ?? 0) > 0 ? (
                    <Button
                      variant="text"
                      size="sm"
                      onClick={() => {
                        const now = new Date()
                        setPeriod(
                          `${now.getFullYear()}-${String(
                            now.getMonth() + 1,
                          ).padStart(2, "0")}`,
                        )
                        setPeriodError(null)
                        setPeriodicTarget(agreement)
                      }}
                    >
                      {t("finance.coaches.accruePeriod")}
                    </Button>
                  ) : null}
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.coaches.earnings")}
        subtitle={t("finance.coaches.earningsHint")}
      >
        {earningsQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : earnings.length === 0 ? (
          <EmptyState
            icon={<ShieldCheck size={24} />}
            title={t("finance.coaches.noEarnings")}
          />
        ) : (
          <div className="stack">
            {earnings.map((earning) => (
              <Card key={earning.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {earning.coach_name ??
                        customerName(earning.coach_user_id)}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>
                        {t("finance.invoice.number")}{" "}
                        {earning.invoice_number
                          ? formatNumber(earning.invoice_number)
                          : "—"}
                      </span>
                      <span>{earning.line_description}</span>
                      <span className="m3-chip">{earning.status}</span>
                      <span>
                        {t("finance.coaches.calculated")}:{" "}
                        {money(earning.calculated_irr)}
                      </span>
                      <span>
                        {t("finance.coaches.vestedAmount")}:{" "}
                        {money(earning.vested_irr)}
                      </span>
                      <span>
                        {t("finance.coaches.eligible")}:{" "}
                        {money(earning.eligible_irr)}
                      </span>
                      <span>
                        {t("finance.coaches.settled")}:{" "}
                        {money(earning.settled_irr)}
                      </span>
                      {(earning.reserved_irr ?? 0) > 0 ? (
                        <span>
                          {t("finance.coaches.reserved")}:{" "}
                          {money(earning.reserved_irr ?? 0)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  {canSettle &&
                  earning.status === "CALCULATED" &&
                  earning.vesting_mode === "MANUAL" &&
                  earning.coach_share_irr > 0 ? (
                    <Button
                      variant="text"
                      size="sm"
                      onClick={() => {
                        setVestReason("")
                        setVestTarget(earning)
                      }}
                    >
                      {t("finance.coaches.vest")}
                    </Button>
                  ) : null}
                  {canAgree && earning.status === "UNRESOLVED" ? (
                    <Button
                      variant="text"
                      size="sm"
                      onClick={() => {
                        setEarningAgreementId("")
                        setEarningResolveReason("")
                        setEarningResolveTarget(earning)
                      }}
                    >
                      {t("finance.coaches.resolveEarning")}
                    </Button>
                  ) : null}
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.coaches.settlements")}
        subtitle={t("finance.coaches.settlementsHint")}
        actions={
          canSettle ? (
            <Button icon={<Plus size={16} />} onClick={openSettlement}>
              {t("finance.coaches.newSettlement")}
            </Button>
          ) : null
        }
      >
        {settlements.length === 0 ? (
          <p className="muted">{t("finance.coaches.noSettlements")}</p>
        ) : (
          <div className="stack">
            {settlements.map((settlement) => (
              <Card key={settlement.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {settlement.coach_name ??
                        customerName(settlement.coach_user_id)}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>{formatDate(settlement.paid_on)}</span>
                      <span className="m3-chip">{settlement.status}</span>
                      <span>{methodLabel(t, settlement.method)}</span>
                      {settlement.reference ? (
                        <span>{settlement.reference}</span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ textAlign: "end" }}>
                    <div>{money(settlement.amount_irr)}</div>
                    {canSettle && settlement.status === "RECORDED" ? (
                      <div
                        className="row"
                        style={{ gap: 4, justifyContent: "end" }}
                      >
                        <Button
                          size="sm"
                          loading={saving}
                          onClick={() => void confirmSettlement(settlement.id)}
                        >
                          {t("finance.coaches.confirm")}
                        </Button>
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => {
                            setCancelReason("")
                            setCancelTarget(settlement)
                          }}
                        >
                          {t("finance.coaches.cancelSettlement")}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.coaches.discrepancies")}
        subtitle={t("finance.coaches.discrepanciesHint")}
      >
        {discrepancies.length === 0 ? (
          <p className="muted">{t("finance.coaches.noDiscrepancies")}</p>
        ) : (
          <div className="stack">
            {discrepancies.map((row) => (
              <Card key={row.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {row.coach_name ?? customerName(row.coach_user_id)}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>
                        {t("finance.invoice.number")}{" "}
                        {row.invoice_number
                          ? formatNumber(row.invoice_number)
                          : "—"}
                      </span>
                      <span className="m3-chip">{row.status}</span>
                      {row.resolution_note ? (
                        <span>{row.resolution_note}</span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ textAlign: "end" }}>
                    <div>{money(row.amount_irr)}</div>
                    {canSettle && row.status === "OPEN" ? (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() => {
                          setResolveNote("")
                          setResolveTarget(row)
                        }}
                      >
                        {t("finance.coaches.resolve")}
                      </Button>
                    ) : null}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <Dialog
        open={agreementOpen}
        title={t("finance.coaches.newAgreement")}
        onClose={() => setAgreementOpen(false)}
        size="lg"
        footer={
          <>
            <Button variant="text" onClick={() => setAgreementOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void createAgreement()}>
              {t("finance.save")}
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
          <SelectField
            label={t("finance.coaches.coach")}
            value={coachId}
            onChange={setCoachId}
            options={coachOptions}
            placeholder={t("finance.chooseCoach")}
            required
          />
          <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
            <DateField
              label={t("finance.coaches.effectiveFrom")}
              value={effectiveFrom}
              onChange={(value) => setEffectiveFrom(value ?? todayIso())}
              required
            />
            <DateField
              label={t("finance.coaches.effectiveTo")}
              value={effectiveTo}
              onChange={setEffectiveTo}
            />
          </div>
          <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
            <SelectField
              label={t("finance.coaches.mode")}
              value={mode}
              onChange={setMode}
              options={[
                { value: "DIRECT", label: "DIRECT" },
                { value: "WATERFALL", label: "WATERFALL" },
              ]}
              containerClassName="grow"
            />
            <SelectField
              label={t("finance.coaches.vestingMode")}
              value={vestingMode}
              onChange={setVestingMode}
              options={[
                { value: "MANUAL", label: "MANUAL" },
                { value: "ON_DATE", label: "ON_DATE" },
              ]}
              containerClassName="grow"
            />
            <TextField
              label={t("finance.coaches.vestingDays")}
              value={vestingDays}
              inputMode="numeric"
              dir="auto"
              onChange={(event) =>
                setVestingDays(normalizeDigits(event.target.value))
              }
            />
          </div>
          <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
            <SelectField
              label={t("finance.coaches.periodicInterval")}
              value={periodicInterval}
              onChange={(value) => setPeriodicInterval(value)}
              options={[
                { value: "NONE", label: t("finance.coaches.periodicNone") },
                {
                  value: "MONTHLY",
                  label: t("finance.coaches.periodicMonthly"),
                },
              ]}
              containerClassName="grow"
            />
            {periodicInterval === "MONTHLY" ? (
              <TextField
                label={t("finance.coaches.periodicAmount")}
                value={periodicFixed}
                inputMode="decimal"
                dir="auto"
                onChange={(event) =>
                  setPeriodicFixed(normalizeDigits(event.target.value))
                }
              />
            ) : null}
          </div>
          <h3 className="m3-section__subtitle">{t("finance.coaches.terms")}</h3>
          {terms.map((term, index) => (
            <div
              key={term.key}
              className="row"
              style={{ gap: 8, alignItems: "flex-end" }}
            >
              <SelectField
                label={t("finance.coaches.recipient")}
                value={term.recipient}
                onChange={(value) =>
                  updateTerm(term.key, {
                    recipient: value as TermRow["recipient"],
                  })
                }
                options={[
                  { value: "COACH", label: "COACH" },
                  ...(isSuperuser
                    ? [{ value: "ASCORA", label: "ASCORA" }]
                    : []),
                  { value: "GYM", label: "GYM" },
                ]}
              />
              <SelectField
                label={t("finance.coaches.basis")}
                value={term.basis}
                onChange={(value) =>
                  updateTerm(term.key, { basis: value as TermRow["basis"] })
                }
                options={[
                  { value: "PERCENT", label: "%" },
                  { value: "FIXED", label: unitLabel },
                ]}
              />
              <TextField
                label={
                  term.basis === "PERCENT"
                    ? t("finance.coaches.percent")
                    : t("finance.amount")
                }
                value={term.value}
                inputMode="decimal"
                dir="auto"
                onChange={(event) =>
                  updateTerm(term.key, {
                    value: normalizeDigits(event.target.value),
                  })
                }
              />
              {terms.length > 1 ? (
                <Button
                  variant="text"
                  aria-label={t("finance.removeLine")}
                  icon={<Trash2 size={16} />}
                  onClick={() =>
                    setTerms((current) =>
                      current.filter((row) => row.key !== term.key),
                    )
                  }
                />
              ) : null}
              {index === terms.length - 1 ? (
                <Button
                  variant="text"
                  size="sm"
                  icon={<Plus size={15} />}
                  onClick={() =>
                    setTerms((current) => [...current, termRow("GYM", "0")])
                  }
                >
                  {t("finance.addLine")}
                </Button>
              ) : null}
            </div>
          ))}
          <label className="row" style={{ gap: 8 }}>
            <input
              type="checkbox"
              checked={activateNow}
              onChange={(event) => setActivateNow(event.target.checked)}
            />
            <span>{t("finance.coaches.activateNow")}</span>
          </label>
        </div>
      </Dialog>

      <Dialog
        open={settlementOpen}
        title={t("finance.coaches.newSettlement")}
        onClose={() => setSettlementOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setSettlementOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void settle()}>
              {t("finance.save")}
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
          <SelectField
            label={t("finance.coaches.coach")}
            value={settleCoachId}
            onChange={setSettleCoachId}
            options={coachOptions}
            placeholder={t("finance.chooseCoach")}
            required
          />
          <TextField
            label={t("finance.amountIn", { unit: unitLabel })}
            value={settleAmount}
            inputMode="decimal"
            dir="auto"
            onChange={(event) =>
              setSettleAmount(normalizeDigits(event.target.value))
            }
            required
          />
          <SelectField
            label={t("finance.refund.method")}
            value={settleMethod}
            onChange={(value) => setSettleMethod(value as PaymentMethod)}
            options={[
              { value: "CASH", label: t("finance.methodCash") },
              { value: "POS", label: t("finance.methodPos") },
              { value: "TRANSFER", label: t("finance.methodTransfer") },
            ]}
          />
          <TextField
            label={t("finance.reference")}
            value={settleReference}
            onChange={(event) => setSettleReference(event.target.value)}
          />
          <DateField
            label={t("finance.coaches.paidOn")}
            value={settleDate}
            onChange={(value) => setSettleDate(value ?? todayIso())}
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={vestTarget !== null}
        title={t("finance.coaches.vest")}
        onClose={() => setVestTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setVestTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={vestReason.trim().length < 3}
              onClick={() => void vest()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <TextField
          label={t("finance.coaches.vestReason")}
          value={vestReason}
          onChange={(event) => setVestReason(event.target.value)}
          multiline
          required
        />
      </Dialog>

      <Dialog
        open={periodicTarget !== null}
        title={t("finance.coaches.accruePeriod")}
        description={
          periodicTarget
            ? (periodicTarget.coach_name ??
              customerName(periodicTarget.coach_user_id))
            : undefined
        }
        onClose={() => setPeriodicTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setPeriodicTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={!period.trim()}
              onClick={() => void accruePeriod()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {periodError ? (
            <div className="m3-inline-alert" role="alert">
              {periodError}
            </div>
          ) : null}
          <TextField
            label={t("finance.coaches.period")}
            helper={t("finance.coaches.periodHint")}
            value={period}
            dir="ltr"
            onChange={(event) => setPeriod(event.target.value)}
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={cancelTarget !== null}
        title={t("finance.coaches.cancelSettlement")}
        onClose={() => setCancelTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setCancelTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={cancelReason.trim().length < 3}
              onClick={() => void cancelSettlement()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <p className="muted">{money(cancelTarget?.amount_irr ?? 0)}</p>
          <TextField
            label={t("finance.coaches.cancelReason")}
            value={cancelReason}
            onChange={(event) => setCancelReason(event.target.value)}
            multiline
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={earningResolveTarget !== null}
        title={t("finance.coaches.resolveEarning")}
        onClose={() => setEarningResolveTarget(null)}
        footer={
          <>
            <Button
              variant="text"
              onClick={() => setEarningResolveTarget(null)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={
                !earningAgreementId || earningResolveReason.trim().length < 3
              }
              onClick={() => void resolveEarning()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <SelectField
            label={t("finance.coaches.selectAgreement")}
            value={earningAgreementId}
            onChange={setEarningAgreementId}
            options={agreements
              .filter(
                (agreement) =>
                  agreement.status === "ACTIVE" &&
                  agreement.coach_user_id ===
                    earningResolveTarget?.coach_user_id,
              )
              .map((agreement) => ({
                value: agreement.id,
                label: `v${formatNumber(agreement.version)} · ${formatDate(
                  agreement.effective_from,
                )}`,
              }))}
            required
          />
          <TextField
            label={t("finance.coaches.resolveReason")}
            value={earningResolveReason}
            onChange={(event) => setEarningResolveReason(event.target.value)}
            multiline
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={resolveTarget !== null}
        title={t("finance.coaches.resolve")}
        onClose={() => setResolveTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setResolveTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={resolveNote.trim().length < 3}
              onClick={() => void resolveDiscrepancy()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <p className="muted">
            {t("finance.coaches.discrepancyAmount")}:{" "}
            {money(resolveTarget?.amount_irr ?? 0)}
          </p>
          <TextField
            label={t("finance.coaches.resolutionNote")}
            value={resolveNote}
            onChange={(event) => setResolveNote(event.target.value)}
            multiline
            required
          />
        </div>
      </Dialog>
    </>
  )
}
