import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FlaskConical, Plus, ReceiptText, RotateCcw } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { translateApiError } from "@/api"
import { DateField } from "@/components/DateField"
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
  createRefund,
  createSale,
  type FinanceCategory,
  listGymCoaches,
  listPayments,
  listSales,
  listTaxes,
  type Payment,
  previewSale,
  type Sale,
  type SalePreview,
  simulatePayment,
  type TaxDefinition,
} from "@/lib/finance-api"
import {
  categoryLabel,
  formatToman,
  partyLabel,
  percentFromBp,
  statusLabel,
  todayIso,
  tomanToIrr,
} from "@/lib/finance-ui"
import { useSnackbar } from "@/snackbar"

const CATEGORY_OPTIONS = (
  ["MEMBERSHIP", "NUTRITION", "TRAINING"] as FinanceCategory[]
).map((value) => ({ value, label: categoryLabel(value) }))

export function FinanceSalesPage({ gymId }: { gymId: string }) {
  const { t, formatNumber, formatDate } = useI18n()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const sales = useQuery({
    queryKey: ["finance-sales", gymId],
    queryFn: () => listSales(gymId),
  })
  const payments = useQuery({
    queryKey: ["finance-payments", gymId],
    queryFn: () => listPayments(gymId),
  })
  const taxes = useQuery({
    queryKey: ["finance-taxes"],
    queryFn: () => listTaxes(),
  })
  const coaches = useQuery({
    queryKey: ["finance-coaches", gymId],
    queryFn: () => listGymCoaches(gymId),
  })
  const [saleOpen, setSaleOpen] = useState(false)
  const [paymentOpen, setPaymentOpen] = useState(false)
  const [createdSale, setCreatedSale] = useState<Sale | null>(null)
  const [paymentResult, setPaymentResult] = useState<Payment | null>(null)
  const [refundTarget, setRefundTarget] = useState<Sale | null>(null)
  const [preview, setPreview] = useState<SalePreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [refundAmount, setRefundAmount] = useState("")
  const [refundReason, setRefundReason] = useState("")
  const [form, setForm] = useState({
    category: "MEMBERSHIP" as FinanceCategory,
    description: "",
    baseToman: "1000000",
    soldOn: todayIso(),
    coachId: "",
    taxIds: [] as string[],
  })

  useEffect(() => {
    if (!taxes.data) return
    setForm((prev) => {
      if (prev.taxIds.length) return prev
      const vat = taxes.data.find((tax) => tax.is_default_vat)
      return vat ? { ...prev, taxIds: [vat.id] } : prev
    })
  }, [taxes.data])

  const baseIrr = tomanToIrr(Number(form.baseToman) || 0)
  const paymentForSale = useMemo(() => {
    if (!refundTarget || !payments.data) return null
    return (
      payments.data.find(
        (row) => row.sale_id === refundTarget.id && row.status === "SUCCEEDED",
      ) ?? null
    )
  }, [payments.data, refundTarget])

  const previewMutation = useMutation({
    mutationFn: () =>
      previewSale(gymId, {
        category: form.category,
        base_amount_irr: baseIrr,
        tax_ids: form.taxIds,
        coach_user_id: form.coachId || null,
        sold_on: form.soldOn,
      }),
    onSuccess: (data) => {
      setPreview(data)
      setError(null)
    },
    onError: (err) => setError(translateApiError(err, t)),
  })

  async function submitSale() {
    if (!form.description.trim()) {
      setError(t("finance.sales.errorDescription"))
      return
    }
    if (baseIrr <= 0) {
      setError(t("finance.sales.errorAmount"))
      return
    }
    setBusy(true)
    setError(null)
    try {
      const sale = await createSale(gymId, {
        category: form.category,
        description: form.description.trim(),
        base_amount_irr: baseIrr,
        tax_ids: form.taxIds,
        coach_user_id: form.coachId || null,
        sold_on: form.soldOn,
      })
      setCreatedSale(sale)
      setPreview(null)
      setSaleOpen(false)
      setPaymentOpen(true)
      await queryClient.invalidateQueries({
        queryKey: ["finance-sales", gymId],
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  async function pay(outcome: "SUCCESS" | "FAILURE" | "CANCELLATION") {
    if (!createdSale) return
    setBusy(true)
    setError(null)
    try {
      const result = await simulatePayment(gymId, createdSale.id, {
        outcome,
        idempotency_key: crypto.randomUUID(),
      })
      setPaymentResult(result)
      await queryClient.invalidateQueries({
        queryKey: ["finance-sales", gymId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["finance-payments", gymId],
      })
      if (result.status === "SUCCEEDED") {
        setCreatedSale((prev) => (prev ? { ...prev, status: "PAID" } : prev))
        show(t("common.success"), "success")
      }
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  async function submitRefund() {
    if (!paymentForSale) return
    const irr = tomanToIrr(Number(refundAmount) || 0)
    if (irr <= 0 || refundReason.trim().length < 3) {
      setError(t("finance.refund.error"))
      return
    }
    setBusy(true)
    setError(null)
    try {
      await createRefund(gymId, paymentForSale.id, {
        amount_irr: irr,
        idempotency_key: crypto.randomUUID(),
        reason: refundReason.trim(),
      })
      setRefundTarget(null)
      setRefundAmount("")
      setRefundReason("")
      await queryClient.invalidateQueries({
        queryKey: ["finance-sales", gymId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["finance-payments", gymId],
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  if (sales.isLoading) return <Spinner label={t("common.loading")} />
  if (sales.isError) {
    return (
      <ErrorState
        message={translateApiError(sales.error, t)}
        onRetry={() => void sales.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={t("finance.sales.title")}
        subtitle={t("finance.sales.subtitle")}
        actions={
          <Button icon={<Plus size={17} />} onClick={() => setSaleOpen(true)}>
            {t("finance.sales.new")}
          </Button>
        }
      />
      <div className="m3-finance-note">
        <FlaskConical size={18} aria-hidden />
        <span>{t("finance.sales.simulationNote")}</span>
      </div>
      {error ? <ErrorState message={error} /> : null}
      {sales.data?.length === 0 ? (
        <EmptyState
          icon={<ReceiptText size={24} />}
          title={t("finance.sales.empty")}
          description={t("finance.sales.emptyHint")}
          action={
            <Button icon={<Plus size={17} />} onClick={() => setSaleOpen(true)}>
              {t("finance.sales.new")}
            </Button>
          }
        />
      ) : (
        <SectionCard title={t("finance.sales.listTitle")}>
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("finance.table.date")}</th>
                  <th>{t("finance.table.description")}</th>
                  <th>{t("finance.table.category")}</th>
                  <th>{t("finance.table.base")}</th>
                  <th>{t("finance.metric.taxes")}</th>
                  <th>{t("finance.table.total")}</th>
                  <th>{t("finance.table.status")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {sales.data?.map((sale) => {
                  const paid = payments.data?.find(
                    (row) =>
                      row.sale_id === sale.id && row.status === "SUCCEEDED",
                  )
                  return (
                    <tr key={sale.id}>
                      <td>{formatDate(sale.sold_on)}</td>
                      <td>{sale.description}</td>
                      <td>{categoryLabel(sale.category)}</td>
                      <td>{formatToman(sale.base_amount_irr, formatNumber)}</td>
                      <td>{formatToman(sale.tax_amount_irr, formatNumber)}</td>
                      <td>
                        {formatToman(sale.total_amount_irr, formatNumber)}
                      </td>
                      <td>
                        <span
                          className={`m3-status m3-status--${sale.status.toLowerCase()}`}
                        >
                          {statusLabel(sale.status)}
                        </span>
                      </td>
                      <td>
                        <div className="m3-inline-actions">
                          {sale.status === "AWAITING_PAYMENT" ? (
                            <Button
                              size="sm"
                              variant="tonal"
                              onClick={() => {
                                setCreatedSale(sale)
                                setPaymentResult(null)
                                setPaymentOpen(true)
                              }}
                            >
                              {t("finance.sales.pay")}
                            </Button>
                          ) : null}
                          {paid ? (
                            <Button
                              size="sm"
                              variant="text"
                              icon={<RotateCcw size={14} />}
                              onClick={() => setRefundTarget(sale)}
                            >
                              {t("finance.sales.refund")}
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <Dialog
        open={saleOpen}
        title={t("finance.sales.dialogTitle")}
        description={t("finance.sales.dialogDescription")}
        onClose={() => setSaleOpen(false)}
        size="lg"
        footer={
          <>
            <Button
              variant="text"
              onClick={() => setSaleOpen(false)}
              disabled={busy}
            >
              {t("common.cancel")}
            </Button>
            <Button
              variant="outlined"
              onClick={() => previewMutation.mutate()}
              loading={previewMutation.isPending}
            >
              {t("finance.sales.calculate")}
            </Button>
            <Button
              onClick={() => void submitSale()}
              loading={busy}
              disabled={!preview}
            >
              {t("finance.sales.create")}
            </Button>
          </>
        }
      >
        <div className="m3-form-grid">
          <SelectField
            label={t("finance.table.category")}
            value={form.category}
            onChange={(value) =>
              setForm((prev) => ({
                ...prev,
                category: value as FinanceCategory,
              }))
            }
            options={CATEGORY_OPTIONS}
          />
          <DateField
            label={t("finance.table.date")}
            value={form.soldOn}
            onChange={(value) => {
              setForm((prev) => ({ ...prev, soldOn: value ?? todayIso() }))
              setPreview(null)
            }}
            maxToday
          />
          <TextField
            label={t("finance.sales.description")}
            value={form.description}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, description: event.target.value }))
            }
            required
          />
          <TextField
            label={t("finance.sales.baseToman")}
            value={form.baseToman}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, baseToman: event.target.value }))
              setPreview(null)
            }}
            inputMode="numeric"
            suffix={t("finance.unit.toman")}
            required
          />
          <SelectField
            label={t("finance.sales.coachOptional")}
            value={form.coachId}
            onChange={(value) => {
              setForm((prev) => ({ ...prev, coachId: value }))
              setPreview(null)
            }}
            options={[
              { value: "", label: t("finance.sales.noCoach") },
              ...(coaches.data ?? []).map((coach) => ({
                value: coach.user_id,
                label: coach.name,
              })),
            ]}
          />
        </div>
        <fieldset className="m3-check-group">
          <legend>{t("finance.sales.applicableTaxes")}</legend>
          {(taxes.data ?? []).map((tax) => (
            <label key={tax.id} className="m3-check">
              <input
                type="checkbox"
                checked={form.taxIds.includes(tax.id)}
                onChange={(event) => {
                  setForm((prev) => ({
                    ...prev,
                    taxIds: event.target.checked
                      ? [...prev.taxIds, tax.id]
                      : prev.taxIds.filter((id) => id !== tax.id),
                  }))
                  setPreview(null)
                }}
              />
              <span>
                {tax.name} — {taxDescription(tax, formatNumber)}
              </span>
            </label>
          ))}
        </fieldset>
        {preview ? <PreviewPanel preview={preview} /> : null}
        {error ? <ErrorState message={error} /> : null}
      </Dialog>

      <Dialog
        open={paymentOpen}
        title={t("finance.payment.dialogTitle")}
        description={t("finance.payment.dialogDescription")}
        onClose={() => {
          setPaymentOpen(false)
          setPaymentResult(null)
        }}
        footer={
          paymentResult?.status === "SUCCEEDED" ? (
            <Button
              onClick={() => {
                setPaymentOpen(false)
                setPaymentResult(null)
              }}
            >
              {t("common.close")}
            </Button>
          ) : (
            <Button
              variant="text"
              onClick={() => setPaymentOpen(false)}
              disabled={busy}
            >
              {t("common.close")}
            </Button>
          )
        }
      >
        {createdSale ? (
          <p className="m3-payment-total">
            {t("finance.payment.amount")}:{" "}
            <strong>
              {formatToman(createdSale.total_amount_irr, formatNumber)}
            </strong>
          </p>
        ) : null}
        <div className="m3-payment-actions">
          <Button onClick={() => void pay("SUCCESS")} loading={busy}>
            {t("finance.payment.success")}
          </Button>
          <Button
            variant="outlined"
            onClick={() => void pay("FAILURE")}
            disabled={busy}
          >
            {t("finance.payment.failure")}
          </Button>
          <Button
            variant="text"
            onClick={() => void pay("CANCELLATION")}
            disabled={busy}
          >
            {t("finance.payment.cancel")}
          </Button>
          {paymentResult && paymentResult.status !== "SUCCEEDED" ? (
            <Button
              variant="tonal"
              onClick={() => void pay("SUCCESS")}
              disabled={busy}
            >
              {t("finance.payment.retry")}
            </Button>
          ) : null}
        </div>
        {paymentResult ? (
          <div className="m3-payment-result">
            <strong>{statusLabel(paymentResult.status)}</strong>
            {paymentResult.status === "SUCCEEDED" ? (
              <div className="m3-table-wrap">
                <table className="m3-table">
                  <thead>
                    <tr>
                      <th>{t("finance.table.party")}</th>
                      <th>{t("finance.table.amount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paymentResult.allocations.map((row) => (
                      <tr key={row.id}>
                        <td>{row.party_name ?? partyLabel(row.party)}</td>
                        <td>{formatToman(row.amount_irr, formatNumber)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>{t("finance.payment.noAllocation")}</p>
            )}
          </div>
        ) : null}
        {error ? <ErrorState message={error} /> : null}
      </Dialog>

      <Dialog
        open={Boolean(refundTarget)}
        title={t("finance.refund.title")}
        description={t("finance.refund.description")}
        onClose={() => setRefundTarget(null)}
        footer={
          <>
            <Button
              variant="text"
              onClick={() => setRefundTarget(null)}
              disabled={busy}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void submitRefund()} loading={busy}>
              {t("finance.refund.submit")}
            </Button>
          </>
        }
      >
        <TextField
          label={t("finance.refund.amountToman")}
          value={refundAmount}
          onChange={(event) => setRefundAmount(event.target.value)}
          inputMode="numeric"
          suffix={t("finance.unit.toman")}
          required
        />
        <TextField
          label={t("finance.refund.reason")}
          value={refundReason}
          onChange={(event) => setRefundReason(event.target.value)}
          required
        />
        <p className="m3-field__message">
          {t("finance.refund.afterSettlement")}
        </p>
        {error ? <ErrorState message={error} /> : null}
      </Dialog>
    </div>
  )
}

function taxDescription(
  tax: TaxDefinition,
  formatNumber: (value: number | string | null | undefined) => string,
) {
  if (tax.calculation === "PERCENT") {
    return `${percentFromBp(tax.percent_bp ?? 0)}٪`
  }
  return `${formatNumber((tax.fixed_amount_irr ?? 0) / 10)} تومان`
}

function PreviewPanel({ preview }: { preview: SalePreview }) {
  const { t, formatNumber } = useI18n()
  return (
    <div className="m3-preview">
      <h3>{t("finance.sales.previewTitle")}</h3>
      <div className="m3-preview__row">
        <span>{t("finance.table.base")}</span>
        <strong>{formatToman(preview.base_amount_irr, formatNumber)}</strong>
      </div>
      {preview.taxes.map((tax) => (
        <div className="m3-preview__row" key={tax.name}>
          <span>{tax.name}</span>
          <strong>{formatToman(tax.amount_irr, formatNumber)}</strong>
        </div>
      ))}
      <div className="m3-preview__row m3-preview__row--total">
        <span>{t("finance.sales.athletePays")}</span>
        <strong>{formatToman(preview.total_amount_irr, formatNumber)}</strong>
      </div>
      <div className="m3-preview__split">
        <Split
          label={t("finance.metric.platformShare")}
          bp={preview.platform_bp}
          amount={preview.platform_amount_irr}
        />
        <Split
          label={t("finance.metric.gymShare")}
          bp={preview.gym_bp}
          amount={preview.gym_amount_irr}
        />
        <Split
          label={t("finance.metric.coachShare")}
          bp={preview.coach_bp}
          amount={preview.coach_amount_irr}
        />
      </div>
      <p className="m3-field__message">
        {t("finance.sales.previewSource", {
          source:
            preview.platform_source === "GYM_OVERRIDE"
              ? t("finance.source.gym")
              : t("finance.source.default"),
        })}
      </p>
    </div>
  )
}

function Split({
  label,
  bp,
  amount,
}: {
  label: string
  bp: number
  amount: number
}) {
  const { formatNumber } = useI18n()
  return (
    <div>
      <span>{label}</span>
      <strong>{percentFromBp(bp)}٪</strong>
      <small>{formatToman(amount, formatNumber)}</small>
    </div>
  )
}
