import { useQuery, useQueryClient } from "@tanstack/react-query"
import { CalendarCheck, Plus } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type FinanceMembershipPublic, FinanceService } from "@/client"
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
  membershipStatusLabel,
  newKey,
  todayIso,
  useFinanceCustomers,
  useMoney,
} from "./shared"

type ActionTarget = FinanceMembershipPublic | null

export function FinanceMembershipsSection({
  settings,
  unit,
}: FinanceSectionProps) {
  const { t, formatDate, formatNumber, normalizeDigits } = useI18n()
  const { activeGymId } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, parse, unitLabel } = useMoney(unit)
  const { customerOptions, customerName } = useFinanceCustomers()
  const canManage = settings.permissions.includes("finance.membership.manage")

  const [open, setOpen] = useState(false)
  const [athleteId, setAthleteId] = useState("")
  const [invoiceId, setInvoiceId] = useState("")
  const [startDate, setStartDate] = useState(todayIso)
  const [endDate, setEndDate] = useState(todayIso)
  const [accessRequired, setAccessRequired] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [freezeTarget, setFreezeTarget] = useState<ActionTarget>(null)
  const [freezeDate, setFreezeDate] = useState(todayIso)
  const [resumeTarget, setResumeTarget] = useState<ActionTarget>(null)
  const [resumeDate, setResumeDate] = useState(todayIso)
  const [cancelTarget, setCancelTarget] = useState<ActionTarget>(null)
  const [cancelDate, setCancelDate] = useState(todayIso)
  const [cancelReason, setCancelReason] = useState("")
  const [transferTarget, setTransferTarget] = useState<ActionTarget>(null)
  const [transferAthleteId, setTransferAthleteId] = useState("")
  const [previewTarget, setPreviewTarget] = useState<ActionTarget>(null)
  const [previewDate, setPreviewDate] = useState(todayIso)

  const scope = activeGymId ?? ""
  const membershipsQuery = useQuery({
    queryKey: ["finance", scope, "memberships"],
    queryFn: async () => (await FinanceService.readFinanceMemberships()).data,
    enabled: Boolean(activeGymId),
  })
  const invoicesQuery = useQuery({
    queryKey: ["finance", scope, "invoices", "ISSUED", "memberships"],
    queryFn: async () =>
      (
        await FinanceService.readFinanceInvoices({
          query: { status: "ISSUED", limit: 50 },
        })
      ).data,
    enabled: Boolean(activeGymId && open),
  })
  const previewQuery = useQuery({
    queryKey: [
      "finance",
      scope,
      "membership-preview",
      previewTarget?.id,
      previewDate,
    ],
    queryFn: async () =>
      (
        await FinanceService.readMembershipRefundPreview({
          path: { membership_id: previewTarget!.id },
          query: { on: previewDate },
        })
      ).data,
    enabled: Boolean(activeGymId && previewTarget),
  })

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["finance", scope] })
  }

  function openCreate() {
    setAthleteId("")
    setInvoiceId("")
    setStartDate(todayIso())
    setEndDate(todayIso())
    setAccessRequired("")
    setFormError(null)
    setOpen(true)
  }

  async function submit() {
    if (!athleteId) {
      setFormError(t("finance.chooseCustomer"))
      return
    }
    const accessIrr = accessRequired ? parse(accessRequired) : 0
    if (accessIrr === null) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    if (accessIrr > 0 && !invoiceId) {
      setFormError(t("errors.membership_invoice_required"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.createFinanceMembership({
        headers: { "Idempotency-Key": newKey() },
        body: {
          athlete_user_id: athleteId,
          invoice_id: invoiceId || null,
          start_date: startDate,
          end_date: endDate,
          access_required_irr: accessIrr,
        },
      })
      await invalidate()
      setOpen(false)
      show(t("finance.membership.created"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function freeze() {
    if (!freezeTarget) return
    setSaving(true)
    try {
      await FinanceService.freezeFinanceMembership({
        path: { membership_id: freezeTarget.id },
        body: { frozen_on: freezeDate },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setFreezeTarget(null)
      show(t("finance.membership.updated"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function resume() {
    if (!resumeTarget) return
    setSaving(true)
    try {
      await FinanceService.resumeFinanceMembership({
        path: { membership_id: resumeTarget.id },
        body: { resume_on: resumeDate },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setResumeTarget(null)
      show(t("finance.membership.updated"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function cancel() {
    if (!cancelTarget) return
    setSaving(true)
    try {
      await FinanceService.cancelFinanceMembership({
        path: { membership_id: cancelTarget.id },
        body: {
          cancelled_on: cancelDate,
          reason: cancelReason.trim() || null,
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setCancelTarget(null)
      setCancelReason("")
      show(t("finance.membership.updated"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function transfer() {
    if (!transferTarget || !transferAthleteId) return
    setSaving(true)
    try {
      await FinanceService.transferFinanceMembership({
        path: { membership_id: transferTarget.id },
        body: { athlete_user_id: transferAthleteId },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setTransferTarget(null)
      show(t("finance.membership.transferred"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  const memberships = membershipsQuery.data?.data ?? []
  const invoices = (invoicesQuery.data?.data ?? []).filter(
    (invoice) => invoice.customer_user_id === athleteId,
  )

  return (
    <>
      <SectionCard
        title={t("finance.membership.title")}
        subtitle={t("finance.membership.subtitle")}
        actions={
          canManage ? (
            <Button icon={<Plus size={16} />} onClick={openCreate}>
              {t("finance.membership.new")}
            </Button>
          ) : null
        }
      >
        {membershipsQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : membershipsQuery.isError ? (
          <ErrorState
            message={translateApiError(membershipsQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => membershipsQuery.refetch()}
          />
        ) : memberships.length === 0 ? (
          <EmptyState
            icon={<CalendarCheck size={24} />}
            title={t("finance.membership.empty")}
          />
        ) : (
          <div className="stack">
            {memberships.map((membership) => (
              <Card key={membership.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>{customerName(membership.athlete_user_id)}</strong>
                    <div className="m3-entity-card__meta">
                      <span
                        className={`m3-status m3-status--${membership.status.toLowerCase()}`}
                      >
                        {membershipStatusLabel(t, membership.status)}
                      </span>
                      <span>
                        {formatDate(membership.start_date)} —{" "}
                        {formatDate(membership.end_date)}
                      </span>
                      <span>
                        {t("finance.invoice.paid")}:{" "}
                        {money(membership.paid_irr)}
                      </span>
                      <span
                        className="m3-chip"
                        style={
                          membership.access_granted
                            ? undefined
                            : { color: "var(--m3-error)" }
                        }
                      >
                        {membership.access_granted
                          ? t("finance.membership.accessGranted")
                          : t("finance.membership.accessBlocked")}
                      </span>
                      {membership.frozen_days > 0 ? (
                        <span>
                          {t("finance.membership.frozen")}:{" "}
                          {formatNumber(membership.frozen_days)}{" "}
                          {t("finance.days")}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ textAlign: "end" }}>
                    {canManage ? (
                      <div
                        className="row"
                        style={{ gap: 4, justifyContent: "end" }}
                      >
                        {membership.status === "ACTIVE" ? (
                          <Button
                            variant="text"
                            size="sm"
                            onClick={() => {
                              setFreezeDate(todayIso())
                              setFreezeTarget(membership)
                            }}
                          >
                            {t("finance.membership.freeze")}
                          </Button>
                        ) : null}
                        {membership.status === "FROZEN" ? (
                          <Button
                            variant="text"
                            size="sm"
                            onClick={() => {
                              setResumeDate(todayIso())
                              setResumeTarget(membership)
                            }}
                          >
                            {t("finance.membership.resume")}
                          </Button>
                        ) : null}
                        {membership.status === "ACTIVE" ||
                        membership.status === "FROZEN" ? (
                          <>
                            <Button
                              variant="text"
                              size="sm"
                              onClick={() => {
                                setTransferTarget(membership)
                                setTransferAthleteId("")
                              }}
                            >
                              {t("finance.membership.transfer")}
                            </Button>
                            <Button
                              variant="text"
                              size="sm"
                              onClick={() => {
                                setCancelDate(todayIso())
                                setCancelReason("")
                                setCancelTarget(membership)
                              }}
                            >
                              {t("finance.membership.cancel")}
                            </Button>
                          </>
                        ) : null}
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => {
                            setPreviewDate(todayIso())
                            setPreviewTarget(membership)
                          }}
                        >
                          {t("finance.membership.preview")}
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

      <Dialog
        open={open}
        title={t("finance.membership.new")}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void submit()}>
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
            label={t("finance.customer")}
            value={athleteId}
            onChange={(value) => {
              setAthleteId(value)
              setInvoiceId("")
            }}
            options={customerOptions}
            placeholder={t("finance.chooseCustomer")}
            required
          />
          <SelectField
            label={t("finance.membership.invoice")}
            value={invoiceId}
            onChange={setInvoiceId}
            options={[
              { value: "", label: t("finance.membership.noInvoice") },
              ...invoices.map((invoice) => ({
                value: invoice.id,
                label: `${
                  invoice.invoice_number ?? t("finance.invoice.draft")
                } · ${money(invoice.balance_irr)}`,
              })),
            ]}
          />
          <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
            <DateField
              label={t("finance.membership.start")}
              value={startDate}
              onChange={(value) => setStartDate(value ?? todayIso())}
              required
            />
            <DateField
              label={t("finance.membership.end")}
              value={endDate}
              onChange={(value) => setEndDate(value ?? todayIso())}
              required
            />
          </div>
          <TextField
            label={`${t("finance.membership.accessRequired")} (${unitLabel})`}
            value={accessRequired}
            inputMode="decimal"
            dir="auto"
            onChange={(event) =>
              setAccessRequired(normalizeDigits(event.target.value))
            }
            helper={t("finance.membership.accessHint")}
          />
        </div>
      </Dialog>

      <Dialog
        open={freezeTarget !== null}
        title={t("finance.membership.freeze")}
        description={
          freezeTarget ? customerName(freezeTarget.athlete_user_id) : undefined
        }
        onClose={() => setFreezeTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setFreezeTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void freeze()}>
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <DateField
          label={t("finance.membership.freezeOn")}
          value={freezeDate}
          onChange={(value) => setFreezeDate(value ?? todayIso())}
          required
        />
      </Dialog>

      <Dialog
        open={resumeTarget !== null}
        title={t("finance.membership.resume")}
        description={
          resumeTarget ? customerName(resumeTarget.athlete_user_id) : undefined
        }
        onClose={() => setResumeTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setResumeTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void resume()}>
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <DateField
          label={t("finance.membership.resumeOn")}
          value={resumeDate}
          onChange={(value) => setResumeDate(value ?? todayIso())}
          required
        />
      </Dialog>

      <Dialog
        open={cancelTarget !== null}
        title={t("finance.membership.cancel")}
        description={
          cancelTarget ? customerName(cancelTarget.athlete_user_id) : undefined
        }
        onClose={() => setCancelTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setCancelTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void cancel()}>
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <DateField
            label={t("finance.membership.cancelOn")}
            value={cancelDate}
            onChange={(value) => setCancelDate(value ?? todayIso())}
            required
          />
          <TextField
            label={t("finance.refund.reason")}
            value={cancelReason}
            onChange={(event) => setCancelReason(event.target.value)}
            multiline
          />
        </div>
      </Dialog>

      <Dialog
        open={transferTarget !== null}
        title={t("finance.membership.transfer")}
        onClose={() => setTransferTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setTransferTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={!transferAthleteId}
              onClick={() => void transfer()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <SelectField
          label={t("finance.customer")}
          value={transferAthleteId}
          onChange={setTransferAthleteId}
          options={customerOptions.filter(
            (option) => option.value !== transferTarget?.athlete_user_id,
          )}
          placeholder={t("finance.chooseCustomer")}
          required
        />
      </Dialog>

      <Dialog
        open={previewTarget !== null}
        title={t("finance.membership.preview")}
        onClose={() => setPreviewTarget(null)}
        footer={
          <Button variant="text" onClick={() => setPreviewTarget(null)}>
            {t("common.close")}
          </Button>
        }
      >
        <div className="stack">
          <DateField
            label={t("finance.membership.previewOn")}
            value={previewDate}
            onChange={(value) => setPreviewDate(value ?? todayIso())}
            required
          />
          {previewQuery.isLoading ? (
            <Spinner label={t("common.loading")} />
          ) : previewQuery.isError ? (
            <ErrorState
              message={translateApiError(previewQuery.error, t)}
              retryLabel={t("common.retry")}
              onRetry={() => previewQuery.refetch()}
            />
          ) : previewQuery.data ? (
            <div className="stack">
              <div className="row row--between">
                <span>{t("finance.membership.proposed")}</span>
                <strong>{money(previewQuery.data.proposed_refund_irr)}</strong>
              </div>
              <div className="row row--between">
                <span>{t("finance.invoice.paid")}</span>
                <span>{money(previewQuery.data.refundable_paid_irr)}</span>
              </div>
              <div className="row row--between">
                <span>{t("finance.membership.unusedDays")}</span>
                <span>
                  {formatNumber(previewQuery.data.unused_days)} /{" "}
                  {formatNumber(previewQuery.data.total_days)}
                </span>
              </div>
            </div>
          ) : null}
        </div>
      </Dialog>
    </>
  )
}
