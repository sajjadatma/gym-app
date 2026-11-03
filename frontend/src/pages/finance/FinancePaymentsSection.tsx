import { useQuery, useQueryClient } from "@tanstack/react-query"
import { CreditCard, Plus, Wallet } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type FinanceBankStatementLinePublic,
  type FinanceCreditPublic,
  type FinanceInvoicePublic,
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

type AllocationRow = { invoiceId: string; amount: string }

function emptyAllocation(): AllocationRow {
  return { invoiceId: "", amount: "" }
}

export function FinancePaymentsSection({
  settings,
  unit,
}: FinanceSectionProps) {
  const { t, formatNumber, formatDate, normalizeDigits } = useI18n()
  const { activeGymId } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, parse, unitLabel } = useMoney(unit)
  const { customerOptions, customerName } = useFinanceCustomers()
  const canRecord = settings.permissions.includes("finance.payment.record")

  const [open, setOpen] = useState(false)
  const [customerId, setCustomerId] = useState("")
  const [method, setMethod] = useState("CASH")
  const [amount, setAmount] = useState("")
  const [receivedOn, setReceivedOn] = useState(todayIso)
  const [reference, setReference] = useState("")
  const [allocations, setAllocations] = useState<AllocationRow[]>([
    emptyAllocation(),
  ])
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [creditTarget, setCreditTarget] = useState<FinanceCreditPublic | null>(
    null,
  )
  const [creditInvoiceId, setCreditInvoiceId] = useState("")
  const [creditAmount, setCreditAmount] = useState("")
  const [creditDate, setCreditDate] = useState(todayIso)
  const [reconciliationOpen, setReconciliationOpen] = useState(false)
  const [statementDate, setStatementDate] = useState(todayIso)
  const [statementAmount, setStatementAmount] = useState("")
  const [statementReference, setStatementReference] = useState("")
  const [matchTarget, setMatchTarget] =
    useState<FinanceBankStatementLinePublic | null>(null)
  const [matchReceiptId, setMatchReceiptId] = useState("")

  const scope = activeGymId ?? ""
  const receiptsQuery = useQuery({
    queryKey: ["finance", scope, "receipts"],
    queryFn: async () =>
      (
        await FinanceService.readFinanceReceipts({
          query: { limit: 50 },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })
  const creditsQuery = useQuery({
    queryKey: ["finance", scope, "credits"],
    queryFn: async () => (await FinanceService.readFinanceCredits()).data,
    enabled: Boolean(activeGymId),
  })
  const reconciliationQuery = useQuery({
    queryKey: ["finance", scope, "reconciliation"],
    queryFn: async () =>
      (await FinanceService.readFinanceReconciliation()).data,
    enabled: Boolean(activeGymId),
  })
  const invoicesQuery = useQuery({
    queryKey: ["finance", scope, "invoices", "ISSUED", "payments"],
    queryFn: async () =>
      (
        await FinanceService.readFinanceInvoices({
          query: { status: "ISSUED", limit: 50 },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })

  const receipts = receiptsQuery.data?.data ?? []
  const credits = creditsQuery.data?.data ?? []
  const openInvoices = (invoicesQuery.data?.data ?? []).filter(
    (invoice) => invoice.balance_irr > 0,
  )
  const customerOpenInvoices = openInvoices.filter(
    (invoice) => invoice.customer_user_id === customerId,
  )
  const creditInvoices = openInvoices.filter(
    (invoice) => invoice.customer_user_id === creditTarget?.customer_user_id,
  )

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["finance", scope] })
  }

  function openRecord() {
    setCustomerId("")
    setMethod("CASH")
    setAmount("")
    setReceivedOn(todayIso())
    setReference("")
    setAllocations([emptyAllocation()])
    setFormError(null)
    setOpen(true)
  }

  function allocationAmount(row: AllocationRow) {
    return parse(row.amount) ?? 0
  }

  function allocationTotal() {
    return allocations.reduce((total, row) => total + allocationAmount(row), 0)
  }

  function setAllocationInvoice(rowIndex: number, invoiceId: string) {
    const invoice = openInvoices.find((item) => item.id === invoiceId)
    setAllocations((current) =>
      current.map((row, index) =>
        index === rowIndex
          ? {
              ...row,
              invoiceId,
              amount:
                row.amount || (invoice ? amountOf(invoice.balance_irr) : ""),
            }
          : row,
      ),
    )
  }

  function amountOf(irr: number) {
    return unit === "TOMAN"
      ? (() => {
          const whole = Math.trunc(irr / 10)
          const fraction = Math.abs(irr % 10)
          return fraction === 0 ? String(whole) : `${whole}.${fraction}`
        })()
      : String(irr)
  }

  async function submit() {
    if (!customerId) {
      setFormError(t("finance.chooseCustomer"))
      return
    }
    const amountIrr = parse(amount)
    if (amountIrr === null || amountIrr <= 0) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    const parsedAllocations = allocations
      .filter((row) => row.invoiceId && row.amount.trim())
      .map((row) => ({
        invoice_id: row.invoiceId,
        amount_irr: parse(row.amount) ?? 0,
      }))
    if (parsedAllocations.some((row) => row.amount_irr <= 0)) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    if (allocationTotal() > amountIrr) {
      setFormError(t("errors.receipt_over_allocated"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.recordFinanceReceipt({
        body: {
          customer_user_id: customerId,
          method: method as "CASH" | "POS" | "TRANSFER",
          amount_irr: amountIrr,
          reference: reference.trim() || null,
          received_on: receivedOn,
          allocations: parsedAllocations,
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setOpen(false)
      show(t("finance.payment.created"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  function openApply(credit: FinanceCreditPublic) {
    setCreditTarget(credit)
    setCreditInvoiceId("")
    setCreditAmount(amountOf(credit.balance_irr))
    setCreditDate(todayIso())
    setFormError(null)
  }

  async function createStatementLine() {
    const amountIrr = parse(statementAmount)
    if (amountIrr === null || amountIrr <= 0) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.createFinanceReconciliationLine({
        body: {
          statement_on: statementDate,
          amount_irr: amountIrr,
          reference: statementReference.trim() || null,
          description: null,
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setReconciliationOpen(false)
      show(t("finance.payment.statementRecorded"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function matchStatement() {
    if (!matchTarget || !matchReceiptId) {
      setFormError(t("finance.payment.chooseReceipt"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.matchFinanceReconciliationLine({
        path: { line_id: matchTarget.id },
        body: { receipt_id: matchReceiptId },
      })
      await invalidate()
      setMatchTarget(null)
      setMatchReceiptId("")
      show(t("finance.payment.reconciled"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function applyCredit() {
    if (!creditTarget || !creditInvoiceId) {
      setFormError(t("errors.invoice_required"))
      return
    }
    const amountIrr = parse(creditAmount)
    if (amountIrr === null || amountIrr <= 0) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.applyFinanceCredit({
        body: {
          customer_user_id: creditTarget.customer_user_id,
          invoice_id: creditInvoiceId,
          amount_irr: amountIrr,
          received_on: creditDate,
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setCreditTarget(null)
      show(t("finance.payment.applied"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <SectionCard
        title={t("finance.payment.title")}
        subtitle={t("finance.payment.subtitle")}
        actions={
          canRecord ? (
            <Button icon={<Plus size={16} />} onClick={openRecord}>
              {t("finance.payment.new")}
            </Button>
          ) : null
        }
      >
        {receiptsQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : receiptsQuery.isError ? (
          <ErrorState
            message={translateApiError(receiptsQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => receiptsQuery.refetch()}
          />
        ) : receipts.length === 0 ? (
          <EmptyState
            icon={<CreditCard size={24} />}
            title={t("finance.payment.empty")}
          />
        ) : (
          <div className="stack">
            {receipts.map((receipt) => (
              <Card key={receipt.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {t("finance.payment.number")}{" "}
                      {formatNumber(receipt.receipt_number)}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>
                        {receipt.customer_name ??
                          customerName(receipt.customer_user_id)}
                      </span>
                      <span>{methodLabel(t, receipt.method)}</span>
                      <span>{formatDate(receipt.received_on)}</span>
                      {receipt.reference ? (
                        <span>
                          {t("finance.reference")}: {receipt.reference}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ textAlign: "end" }}>
                    <div>{money(receipt.amount_irr)}</div>
                    <div className="muted">
                      {t("finance.payment.allocated")}:{" "}
                      {money(receipt.allocated_irr)}
                    </div>
                    {receipt.excess_irr > 0 ? (
                      <div className="muted">
                        {t("finance.payment.excess")}:{" "}
                        {money(receipt.excess_irr)}
                      </div>
                    ) : null}
                  </div>
                </div>
                {receipt.allocations.length > 0 ? (
                  <div className="m3-entity-card__meta">
                    {receipt.allocations.map((allocation) => (
                      <span key={allocation.invoice_id}>
                        {t("finance.invoice.number")}{" "}
                        {allocation.invoice_number
                          ? formatNumber(allocation.invoice_number)
                          : "—"}{" "}
                        · {money(allocation.amount_irr)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.payment.credits")}
        subtitle={t("finance.payment.creditsHint")}
      >
        {creditsQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : creditsQuery.isError ? (
          <ErrorState
            message={translateApiError(creditsQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => creditsQuery.refetch()}
          />
        ) : credits.length === 0 ? (
          <EmptyState
            icon={<Wallet size={24} />}
            title={t("finance.payment.creditsEmpty")}
          />
        ) : (
          <div className="stack">
            {credits.map((credit) => (
              <div key={credit.customer_user_id} className="row row--between">
                <div>
                  <strong>
                    {credit.customer_name ??
                      customerName(credit.customer_user_id)}
                  </strong>
                  <div className="muted">{money(credit.balance_irr)}</div>
                </div>
                {canRecord ? (
                  <Button
                    variant="text"
                    size="sm"
                    onClick={() => openApply(credit)}
                  >
                    {t("finance.payment.apply")}
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.payment.reconciliation")}
        subtitle={t("finance.payment.reconciliationHint")}
        actions={
          canRecord ? (
            <Button
              icon={<Plus size={16} />}
              onClick={() => {
                setStatementDate(todayIso())
                setStatementAmount("")
                setStatementReference("")
                setFormError(null)
                setReconciliationOpen(true)
              }}
            >
              {t("finance.payment.newStatementLine")}
            </Button>
          ) : null
        }
      >
        {reconciliationQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : (reconciliationQuery.data?.data ?? []).length === 0 ? (
          <p className="muted">{t("finance.payment.noStatementLines")}</p>
        ) : (
          <div className="stack">
            {(reconciliationQuery.data?.data ?? []).map((line) => (
              <div key={line.id} className="row row--between">
                <div>
                  <strong>{money(line.amount_irr)}</strong>
                  <div className="m3-entity-card__meta">
                    <span>{formatDate(line.statement_on)}</span>
                    <span
                      className="m3-chip"
                      style={
                        line.status === "UNMATCHED"
                          ? { color: "var(--m3-error)" }
                          : undefined
                      }
                    >
                      {line.status}
                    </span>
                    {line.reference ? <span>{line.reference}</span> : null}
                    {line.receipt_number ? (
                      <span>
                        {t("finance.payment.number")}{" "}
                        {formatNumber(line.receipt_number)}
                      </span>
                    ) : null}
                  </div>
                </div>
                {canRecord && line.status === "UNMATCHED" ? (
                  <Button
                    variant="text"
                    size="sm"
                    onClick={() => {
                      setMatchReceiptId("")
                      setFormError(null)
                      setMatchTarget({
                        ...line,
                        reference: line.reference ?? null,
                      })
                    }}
                  >
                    {t("finance.payment.match")}
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <Dialog
        open={reconciliationOpen}
        title={t("finance.payment.newStatementLine")}
        onClose={() => setReconciliationOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setReconciliationOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void createStatementLine()}>
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
          <DateField
            label={t("finance.expense.spentOn")}
            value={statementDate}
            onChange={(value) => setStatementDate(value ?? todayIso())}
            required
          />
          <TextField
            label={t("finance.amountIn", { unit: unitLabel })}
            value={statementAmount}
            inputMode="decimal"
            dir="auto"
            onChange={(event) =>
              setStatementAmount(normalizeDigits(event.target.value))
            }
            required
          />
          <TextField
            label={t("finance.reference")}
            value={statementReference}
            onChange={(event) => setStatementReference(event.target.value)}
          />
        </div>
      </Dialog>

      <Dialog
        open={matchTarget !== null}
        title={t("finance.payment.match")}
        description={
          matchTarget
            ? `${money(matchTarget.amount_irr)} ${t("finance.reference")}: ${matchTarget.reference ?? "—"}`
            : undefined
        }
        onClose={() => setMatchTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setMatchTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void matchStatement()}>
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
          <SelectField
            label={t("finance.payment.matchReceipt")}
            value={matchReceiptId}
            onChange={setMatchReceiptId}
            options={receipts
              .filter((receipt) => !receipt.reconciled)
              .map((receipt) => ({
                value: receipt.id,
                label: `#${formatNumber(receipt.receipt_number)} · ${money(
                  receipt.amount_irr,
                )}`,
              }))}
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={open}
        title={t("finance.payment.new")}
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
            label={t("finance.customer")}
            value={customerId}
            onChange={(value) => {
              setCustomerId(value)
              setAllocations([emptyAllocation()])
            }}
            options={customerOptions}
            placeholder={t("finance.chooseCustomer")}
            required
          />
          <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
            <SelectField
              label={t("finance.refund.method")}
              value={method}
              onChange={setMethod}
              options={[
                { value: "CASH", label: t("finance.methodCash") },
                { value: "POS", label: t("finance.methodPos") },
                { value: "TRANSFER", label: t("finance.methodTransfer") },
              ]}
            />
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
            <DateField
              label={t("finance.expense.spentOn")}
              value={receivedOn}
              onChange={(value) => setReceivedOn(value ?? todayIso())}
              required
            />
          </div>
          <TextField
            label={t("finance.reference")}
            value={reference}
            onChange={(event) => setReference(event.target.value)}
          />

          <h3 className="m3-section__subtitle">
            {t("finance.payment.allocations")}
          </h3>
          {customerId && customerOpenInvoices.length === 0 ? (
            <p className="muted">{t("finance.payment.noOpenInvoices")}</p>
          ) : null}
          {allocations.map((row, index) => (
            <div
              key={`${row.invoiceId}-${index}`}
              className="row"
              style={{ gap: 8, alignItems: "flex-end" }}
            >
              <SelectField
                label={t("finance.invoice.title")}
                value={row.invoiceId}
                onChange={(value) => setAllocationInvoice(index, value)}
                options={[
                  { value: "", label: t("finance.payment.unallocated") },
                  ...customerOpenInvoices.map(
                    (invoice: FinanceInvoicePublic) => ({
                      value: invoice.id,
                      label: `${
                        invoice.invoice_number
                          ? formatNumber(invoice.invoice_number)
                          : t("finance.invoice.draft")
                      } · ${money(invoice.balance_irr)}`,
                    }),
                  ),
                ]}
                containerClassName="grow"
              />
              <TextField
                label={t("finance.amountIn", { unit: unitLabel })}
                value={row.amount}
                inputMode="decimal"
                dir="auto"
                onChange={(event) =>
                  setAllocations((current) =>
                    current.map((item, itemIndex) =>
                      itemIndex === index
                        ? {
                            ...item,
                            amount: normalizeDigits(event.target.value),
                          }
                        : item,
                    ),
                  )
                }
              />
            </div>
          ))}
          <div className="row row--between">
            <Button
              variant="text"
              size="sm"
              icon={<Plus size={15} />}
              onClick={() =>
                setAllocations((current) => [...current, emptyAllocation()])
              }
            >
              {t("finance.payment.allocate")}
            </Button>
            <span className="muted">
              {t("finance.payment.allocated")}: {money(allocationTotal())}
            </span>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={creditTarget !== null}
        title={t("finance.payment.apply")}
        description={
          creditTarget ? customerName(creditTarget.customer_user_id) : undefined
        }
        onClose={() => setCreditTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setCreditTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void applyCredit()}>
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
          <SelectField
            label={t("finance.invoice.title")}
            value={creditInvoiceId}
            onChange={setCreditInvoiceId}
            options={creditInvoices.map((invoice) => ({
              value: invoice.id,
              label: `${
                invoice.invoice_number
                  ? formatNumber(invoice.invoice_number)
                  : t("finance.invoice.draft")
              } · ${money(invoice.balance_irr)}`,
            }))}
            required
          />
          <TextField
            label={t("finance.amountIn", { unit: unitLabel })}
            value={creditAmount}
            inputMode="decimal"
            dir="auto"
            onChange={(event) =>
              setCreditAmount(normalizeDigits(event.target.value))
            }
            required
          />
          <DateField
            label={t("finance.expense.spentOn")}
            value={creditDate}
            onChange={(value) => setCreditDate(value ?? todayIso())}
            required
          />
        </div>
      </Dialog>
    </>
  )
}
