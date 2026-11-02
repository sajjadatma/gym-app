import { useQuery, useQueryClient } from "@tanstack/react-query"
import { HandCoins, Plus } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type FinanceRefundPublic, FinanceService } from "@/client"
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
  refundStatusLabel,
  todayIso,
  useFinanceCustomers,
  useMoney,
} from "./shared"

export function FinanceRefundsSection({ settings, unit }: FinanceSectionProps) {
  const { t, formatDate, normalizeDigits } = useI18n()
  const { activeGymId } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, parse, unitLabel } = useMoney(unit)
  const { customerOptions, customerName } = useFinanceCustomers()
  const canManage = settings.permissions.includes("finance.refund.manage")

  const [open, setOpen] = useState(false)
  const [source, setSource] = useState<"INVOICE" | "ADVANCE">("INVOICE")
  const [customerId, setCustomerId] = useState("")
  const [invoiceId, setInvoiceId] = useState("")
  const [amount, setAmount] = useState("")
  const [method, setMethod] = useState("")
  const [overrideReason, setOverrideReason] = useState("")
  const [reason, setReason] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [rejectTarget, setRejectTarget] = useState<FinanceRefundPublic | null>(
    null,
  )
  const [rejectReason, setRejectReason] = useState("")
  const [recordTarget, setRecordTarget] = useState<FinanceRefundPublic | null>(
    null,
  )
  const [recordDate, setRecordDate] = useState(todayIso)

  const scope = activeGymId ?? ""
  const refundsQuery = useQuery({
    queryKey: ["finance", scope, "refunds"],
    queryFn: async () => (await FinanceService.readFinanceRefunds()).data,
    enabled: Boolean(activeGymId),
  })
  const invoicesQuery = useQuery({
    queryKey: ["finance", scope, "invoices", "ISSUED", "refunds"],
    queryFn: async () =>
      (
        await FinanceService.readFinanceInvoices({
          query: { status: "ISSUED", limit: 50 },
        })
      ).data,
    enabled: Boolean(activeGymId && open),
  })
  const creditsQuery = useQuery({
    queryKey: ["finance", scope, "credits", "refunds"],
    queryFn: async () => (await FinanceService.readFinanceCredits()).data,
    enabled: Boolean(activeGymId && open),
  })
  const receiptsQuery = useQuery({
    queryKey: ["finance", scope, "receipts", "refunds"],
    queryFn: async () =>
      (
        await FinanceService.readFinanceReceipts({
          query: { limit: 50 },
        })
      ).data,
    enabled: Boolean(activeGymId && open),
  })

  const refunds = refundsQuery.data?.data ?? []
  const invoices = (invoicesQuery.data?.data ?? []).filter(
    (invoice) =>
      invoice.customer_user_id === customerId && invoice.paid_irr > 0,
  )
  const credit = (creditsQuery.data?.data ?? []).find(
    (item) => item.customer_user_id === customerId,
  )
  const originalMethod =
    source === "INVOICE"
      ? (receiptsQuery.data?.data ?? []).find((receipt) =>
          receipt.allocations.some(
            (allocation) => allocation.invoice_id === invoiceId,
          ),
        )?.method
      : (receiptsQuery.data?.data ?? []).find(
          (receipt) =>
            receipt.customer_user_id === customerId && receipt.excess_irr > 0,
        )?.method

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["finance", scope] })
  }

  function openRequest() {
    setSource("INVOICE")
    setCustomerId("")
    setInvoiceId("")
    setAmount("")
    setMethod("")
    setOverrideReason("")
    setReason("")
    setFormError(null)
    setOpen(true)
  }

  async function submit() {
    if (!customerId) {
      setFormError(t("finance.chooseCustomer"))
      return
    }
    if (source === "INVOICE" && !invoiceId) {
      setFormError(t("errors.invoice_required"))
      return
    }
    const amountIrr = parse(amount)
    if (amountIrr === null || amountIrr <= 0) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    if (reason.trim().length < 3) {
      setFormError(t("finance.refund.reasonRequired"))
      return
    }
    if (
      method &&
      originalMethod &&
      method !== originalMethod &&
      !overrideReason.trim()
    ) {
      setFormError(t("errors.refund_method_reason_required"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.requestFinanceRefund({
        body: {
          source,
          customer_user_id: customerId,
          invoice_id: source === "INVOICE" ? invoiceId : null,
          amount_irr: amountIrr,
          method: method ? (method as "CASH" | "POS" | "TRANSFER") : null,
          method_override_reason: overrideReason.trim() || null,
          reason: reason.trim(),
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setOpen(false)
      show(t("finance.refund.requested"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function approve(refund: FinanceRefundPublic) {
    setSaving(true)
    try {
      await FinanceService.approveFinanceRefund({
        path: { refund_id: refund.id },
      })
      await invalidate()
      show(t("finance.refund.statusApproved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function reject() {
    if (!rejectTarget) return
    setSaving(true)
    try {
      await FinanceService.rejectFinanceRefund({
        path: { refund_id: rejectTarget.id },
        body: { reason: rejectReason.trim() },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setRejectTarget(null)
      setRejectReason("")
      show(t("finance.refund.statusRejected"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function record() {
    if (!recordTarget) return
    setSaving(true)
    try {
      await FinanceService.recordFinanceRefund({
        path: { refund_id: recordTarget.id },
        body: { posting_date: recordDate },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setRecordTarget(null)
      show(t("finance.refund.recorded"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  const methodOptions = [
    { value: "", label: t("finance.refund.useOriginal") },
    { value: "CASH", label: t("finance.methodCash") },
    { value: "POS", label: t("finance.methodPos") },
    { value: "TRANSFER", label: t("finance.methodTransfer") },
  ]

  return (
    <>
      <SectionCard
        title={t("finance.refund.title")}
        subtitle={t("finance.refund.subtitle")}
        actions={
          canManage ? (
            <Button icon={<Plus size={16} />} onClick={openRequest}>
              {t("finance.refund.new")}
            </Button>
          ) : null
        }
      >
        {refundsQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : refundsQuery.isError ? (
          <ErrorState
            message={translateApiError(refundsQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => refundsQuery.refetch()}
          />
        ) : refunds.length === 0 ? (
          <EmptyState
            icon={<HandCoins size={24} />}
            title={t("finance.refund.empty")}
          />
        ) : (
          <div className="stack">
            {refunds.map((refund) => (
              <Card key={refund.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>{customerName(refund.customer_user_id)}</strong>
                    <div className="m3-entity-card__meta">
                      <span
                        className={`m3-status m3-status--${refund.status.toLowerCase()}`}
                      >
                        {refundStatusLabel(t, refund.status)}
                      </span>
                      <span>
                        {refund.source === "INVOICE"
                          ? t("finance.refund.sourceInvoice")
                          : t("finance.refund.sourceAdvance")}
                      </span>
                      <span>{formatDate(refund.created_at.slice(0, 10))}</span>
                      <span>
                        {t("finance.refund.method")}:{" "}
                        {methodLabel(t, refund.method)}
                      </span>
                      {refund.original_method &&
                      refund.original_method !== refund.method ? (
                        <span>
                          {t("finance.refund.originalMethod")}:{" "}
                          {methodLabel(t, refund.original_method)}
                        </span>
                      ) : null}
                    </div>
                    <p className="muted">{refund.reason}</p>
                    {refund.method_override_reason ? (
                      <p className="muted">
                        {t("finance.refund.overrideReason")}:{" "}
                        {refund.method_override_reason}
                      </p>
                    ) : null}
                  </div>
                  <div style={{ textAlign: "end" }}>
                    <div>{money(refund.amount_irr)}</div>
                    {canManage && refund.status === "REQUESTED" ? (
                      <div
                        className="row"
                        style={{ gap: 4, justifyContent: "end" }}
                      >
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => void approve(refund)}
                        >
                          {t("finance.refund.approve")}
                        </Button>
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => {
                            setRejectReason("")
                            setRejectTarget(refund)
                          }}
                        >
                          {t("finance.refund.reject")}
                        </Button>
                      </div>
                    ) : null}
                    {canManage && refund.status === "APPROVED" ? (
                      <Button
                        size="sm"
                        onClick={() => {
                          setRecordDate(todayIso())
                          setRecordTarget(refund)
                        }}
                      >
                        {t("finance.refund.record")}
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
        open={open}
        title={t("finance.refund.new")}
        onClose={() => setOpen(false)}
        size="lg"
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
            label={t("finance.refund.source")}
            value={source}
            onChange={(value) => {
              setSource(value as "INVOICE" | "ADVANCE")
              setInvoiceId("")
            }}
            options={[
              {
                value: "INVOICE",
                label: t("finance.refund.sourceInvoice"),
              },
              {
                value: "ADVANCE",
                label: t("finance.refund.sourceAdvance"),
              },
            ]}
          />
          <SelectField
            label={t("finance.customer")}
            value={customerId}
            onChange={(value) => {
              setCustomerId(value)
              setInvoiceId("")
            }}
            options={customerOptions}
            placeholder={t("finance.chooseCustomer")}
            required
          />
          {source === "INVOICE" ? (
            <SelectField
              label={t("finance.invoice.title")}
              value={invoiceId}
              onChange={(value) => {
                setInvoiceId(value)
                const invoice = invoices.find((item) => item.id === value)
                if (invoice) {
                  setAmount(
                    unit === "TOMAN"
                      ? String(Math.trunc(invoice.balance_irr / 10))
                      : String(invoice.balance_irr),
                  )
                }
              }}
              options={invoices.map((invoice) => ({
                value: invoice.id,
                label: `${
                  invoice.invoice_number ?? t("finance.invoice.draft")
                } · ${money(invoice.balance_irr)}`,
              }))}
              required
            />
          ) : (
            <p className="muted">
              {t("finance.payment.excess")}: {money(credit?.balance_irr ?? 0)}
            </p>
          )}
          <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
            <TextField
              label={t("finance.amountIn", { unit: unitLabel })}
              value={amount}
              inputMode="decimal"
              dir="auto"
              onChange={(event) =>
                setAmount(normalizeDigits(event.target.value))
              }
              required
            />
            <SelectField
              label={t("finance.refund.method")}
              value={method}
              onChange={setMethod}
              options={methodOptions}
              helper={t("finance.refund.defaultMethodHint")}
            />
          </div>
          {originalMethod ? (
            <p className="muted">
              {t("finance.refund.originalMethod")}:{" "}
              {methodLabel(t, originalMethod)}
            </p>
          ) : null}
          {method && originalMethod && method !== originalMethod ? (
            <TextField
              label={t("finance.refund.overrideReason")}
              value={overrideReason}
              onChange={(event) => setOverrideReason(event.target.value)}
              required
            />
          ) : null}
          <TextField
            label={t("finance.refund.reason")}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            multiline
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={rejectTarget !== null}
        title={t("finance.refund.reject")}
        onClose={() => setRejectTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setRejectTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={rejectReason.trim().length < 3}
              onClick={() => void reject()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <TextField
          label={t("finance.refund.rejectReason")}
          value={rejectReason}
          onChange={(event) => setRejectReason(event.target.value)}
          multiline
          required
        />
      </Dialog>

      <Dialog
        open={recordTarget !== null}
        title={t("finance.refund.record")}
        onClose={() => setRecordTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setRecordTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void record()}>
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <DateField
          label={t("finance.postingDate")}
          value={recordDate}
          onChange={(value) => setRecordDate(value ?? todayIso())}
          required
        />
      </Dialog>
    </>
  )
}
