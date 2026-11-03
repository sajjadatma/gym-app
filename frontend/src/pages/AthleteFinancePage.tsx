import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  BellRing,
  CalendarCheck,
  CreditCard,
  FileText,
  HandCoins,
  Wallet,
} from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { FinanceService } from "@/client"
import {
  Button,
  Card,
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
import { formatIrr } from "@/lib/money"
import { useSnackbar } from "@/snackbar"
import {
  membershipStatusLabel,
  methodLabel,
  refundStatusLabel,
  useMoney,
} from "./finance/shared"

export function AthleteFinancePage() {
  const { t, formatDate, formatNumber, normalizeDigits } = useI18n()
  const { activeGym, activeGymId, activeRole } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, unitLabel } = useMoney("RIAL")

  const [open, setOpen] = useState(false)
  const [invoiceId, setInvoiceId] = useState("")
  const [amount, setAmount] = useState("")
  const [method, setMethod] = useState("")
  const [overrideReason, setOverrideReason] = useState("")
  const [reason, setReason] = useState("")
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const accountQuery = useQuery({
    queryKey: ["finance", activeGymId, "my-account"],
    queryFn: async () => (await FinanceService.readMyFinanceAccount()).data,
    enabled: Boolean(activeGymId && activeRole === "ATHLETE"),
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("finance.my.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }
  if (activeRole !== "ATHLETE") {
    return (
      <>
        <PageHeader
          title={t("finance.my.title")}
          subtitle={t("finance.my.subtitle")}
        />
        <ErrorState message={t("errors.athlete_staff_access_required")} />
      </>
    )
  }
  if (accountQuery.isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (accountQuery.isError) {
    return (
      <ErrorState
        message={translateApiError(accountQuery.error, t)}
        retryLabel={t("common.retry")}
        onRetry={() => accountQuery.refetch()}
      />
    )
  }

  const account = accountQuery.data!
  const unit = "RIAL" as const
  const refundableInvoices = account.invoices.filter(
    (invoice) => invoice.paid_irr > 0,
  )
  const selectedInvoice = refundableInvoices.find(
    (invoice) => invoice.id === invoiceId,
  )
  const dueTotal = account.invoices.reduce(
    (sum, invoice) => sum + invoice.balance_irr,
    0,
  )
  const overdueCount = account.invoices.filter(
    (invoice) => invoice.overdue,
  ).length
  const originalMethod = account.receipts.find((receipt) =>
    receipt.allocations.some(
      (allocation) => allocation.invoice_id === invoiceId,
    ),
  )?.method

  function openRequest(invoice?: { id: string; paid_irr: number }) {
    setInvoiceId(invoice?.id ?? "")
    setAmount(
      invoice
        ? formatIrr(invoice.paid_irr, unit, (value) => String(value)).replace(
            /[,،]/g,
            "",
          )
        : "",
    )
    setMethod("")
    setOverrideReason("")
    setReason("")
    setFormError(null)
    setOpen(true)
  }

  async function submit() {
    if (!invoiceId) {
      setFormError(t("errors.invoice_required"))
      return
    }
    const amountIrr = Number(normalizeDigits(amount))
    if (!Number.isSafeInteger(amountIrr) || amountIrr <= 0) {
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
      await FinanceService.requestMyFinanceRefund({
        body: {
          invoice_id: invoiceId,
          amount_irr: amountIrr,
          method: method ? (method as "CASH" | "POS" | "TRANSFER") : null,
          method_override_reason: overrideReason.trim() || null,
          reason: reason.trim(),
        },
      })
      await queryClient.invalidateQueries({
        queryKey: ["finance", activeGymId, "my-account"],
      })
      setOpen(false)
      show(t("finance.refund.requested"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t("finance.my.title")}
        subtitle={`${activeGym.name} · ${t("finance.my.subtitle")}`}
      />

      <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
        <Card variant="outlined">
          <div className="m3-entity-card__meta">
            <Wallet size={16} />
            <span>{t("finance.my.advance")}</span>
          </div>
          <strong>{money(account.advance_balance_irr)}</strong>
        </Card>
        <Card variant="outlined">
          <div className="m3-entity-card__meta">
            <FileText size={16} />
            <span>{t("finance.my.due")}</span>
          </div>
          <strong>{money(dueTotal)}</strong>
          {overdueCount > 0 ? (
            <div className="muted">
              {t("finance.my.overdueCount", { count: overdueCount })}
            </div>
          ) : null}
        </Card>
        <Card variant="outlined">
          <div className="m3-entity-card__meta">
            <CalendarCheck size={16} />
            <span>{t("finance.my.membership")}</span>
          </div>
          {account.memberships[0] ? (
            <>
              <strong>
                {membershipStatusLabel(t, account.memberships[0].status)}
              </strong>
              <div className="muted">
                {formatDate(account.memberships[0].end_date)}
              </div>
            </>
          ) : (
            <span className="muted">{t("finance.my.noMembership")}</span>
          )}
        </Card>
      </div>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.reminders")}
        subtitle={t("finance.remindersHint")}
      >
        {account.reminders.installments.length === 0 &&
        account.reminders.renewals.length === 0 ? (
          <EmptyState
            icon={<BellRing size={24} />}
            title={t("finance.remindersEmpty")}
          />
        ) : (
          <div className="stack">
            {account.reminders.installments.map((item) => (
              <div
                key={`${item.invoice_id}-${item.due_date}`}
                className="row row--between"
              >
                <div>
                  <strong>
                    {t("finance.invoice.number")}{" "}
                    {item.invoice_number
                      ? formatNumber(item.invoice_number)
                      : "—"}
                  </strong>
                  <div className="muted">{formatDate(item.due_date)}</div>
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
            ))}
            {account.reminders.renewals.map((item) => (
              <div key={item.membership_id} className="row row--between">
                <span>{t("finance.membership.title")}</span>
                <div className="row" style={{ gap: 8 }}>
                  <span>{formatDate(item.end_date)}</span>
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
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.my.invoices")}
        subtitle={t("finance.my.subtitle")}
        actions={
          refundableInvoices.length > 0 ? (
            <Button variant="tonal" onClick={() => openRequest()}>
              {t("finance.my.requestRefund")}
            </Button>
          ) : null
        }
      >
        {account.invoices.length === 0 ? (
          <EmptyState
            icon={<FileText size={24} />}
            title={t("finance.invoice.empty")}
          />
        ) : (
          <div className="stack">
            {account.invoices.map((invoice) => (
              <Card key={invoice.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {invoice.invoice_number
                        ? `${t("finance.invoice.number")} ${formatNumber(invoice.invoice_number)}`
                        : t("finance.invoice.draft")}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span
                        className={`m3-status m3-status--${invoice.status.toLowerCase()}`}
                      >
                        {invoice.status === "ISSUED"
                          ? t("finance.invoice.issued")
                          : invoice.status === "VOID"
                            ? t("finance.invoice.void")
                            : t("finance.invoice.draft")}
                      </span>
                      {invoice.issue_date ? (
                        <span>{formatDate(invoice.issue_date)}</span>
                      ) : null}
                      {invoice.overdue ? (
                        <span style={{ color: "var(--m3-error)" }}>
                          {t("finance.overdue")}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ textAlign: "end" }}>
                    <div>{money(invoice.total_irr)}</div>
                    <div className="muted">
                      {t("finance.invoice.balance")}:{" "}
                      {money(invoice.balance_irr)}
                    </div>
                    {invoice.paid_irr > 0 && invoice.status === "ISSUED" ? (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() =>
                          openRequest({
                            id: invoice.id,
                            paid_irr: invoice.paid_irr,
                          })
                        }
                      >
                        {t("finance.my.requestRefund")}
                      </Button>
                    ) : null}
                  </div>
                </div>
                <div className="m3-table-wrap">
                  <table className="m3-table">
                    <thead>
                      <tr>
                        <th>{t("finance.description")}</th>
                        <th>{t("finance.quantity")}</th>
                        <th>{t("finance.invoice.total")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoice.lines.map((line) => (
                        <tr key={line.id}>
                          <td>{line.description}</td>
                          <td>{formatNumber(line.quantity)}</td>
                          <td>{money(line.net_irr)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {invoice.installments.length > 0 ? (
                  <div className="m3-table-wrap">
                    <table className="m3-table">
                      <thead>
                        <tr>
                          <th>{t("finance.invoice.dueDate")}</th>
                          <th>{t("finance.amount")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {invoice.installments.map((item) => (
                          <tr key={item.id}>
                            <td>{formatDate(item.due_date)}</td>
                            <td>{money(item.amount_irr)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.my.receipts")}
        subtitle={t("finance.my.subtitle")}
      >
        {account.receipts.length === 0 ? (
          <EmptyState
            icon={<CreditCard size={24} />}
            title={t("finance.payment.empty")}
          />
        ) : (
          <div className="stack">
            {account.receipts.map((receipt) => (
              <div key={receipt.id} className="row row--between">
                <div>
                  <strong>
                    {t("finance.payment.number")}{" "}
                    {formatNumber(receipt.receipt_number)}
                  </strong>
                  <div className="muted">
                    {formatDate(receipt.received_on)} ·{" "}
                    {methodLabel(t, receipt.method)}
                    {receipt.reference
                      ? ` · ${t("finance.reference")}: ${receipt.reference}`
                      : ""}
                  </div>
                </div>
                <span>{money(receipt.amount_irr)}</span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.membership.title")}
        subtitle={t("finance.my.membership")}
      >
        {account.memberships.length === 0 ? (
          <p className="muted">{t("finance.my.noMembership")}</p>
        ) : (
          <div className="stack">
            {account.memberships.map((membership) => (
              <Card key={membership.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {membershipStatusLabel(t, membership.status)}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>
                        {formatDate(membership.start_date)} —{" "}
                        {formatDate(membership.end_date)}
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
                    </div>
                  </div>
                  <span>{money(membership.paid_irr)}</span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.refund.title")}
        subtitle={t("finance.refund.subtitle")}
      >
        {account.refunds.length === 0 ? (
          <EmptyState
            icon={<HandCoins size={24} />}
            title={t("finance.refund.empty")}
          />
        ) : (
          <div className="stack">
            {account.refunds.map((refund) => (
              <div key={refund.id} className="row row--between">
                <div>
                  <strong>{money(refund.amount_irr)}</strong>
                  <div className="muted">{refund.reason}</div>
                  <div className="m3-entity-card__meta">
                    <span
                      className={`m3-status m3-status--${refund.status.toLowerCase()}`}
                    >
                      {refundStatusLabel(t, refund.status)}
                    </span>
                    <span>{methodLabel(t, refund.method)}</span>
                  </div>
                </div>
                <span>{formatDate(refund.created_at.slice(0, 10))}</span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <Dialog
        open={open}
        title={t("finance.my.requestRefund")}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void submit()}>
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
            value={invoiceId}
            onChange={(value) => {
              setInvoiceId(value)
              const invoice = refundableInvoices.find(
                (item) => item.id === value,
              )
              if (invoice) {
                setAmount(
                  formatIrr(invoice.paid_irr, unit, (input) => String(input)),
                )
              }
            }}
            options={refundableInvoices.map((invoice) => ({
              value: invoice.id,
              label: `${
                invoice.invoice_number ?? t("finance.invoice.draft")
              } · ${money(invoice.paid_irr)}`,
            }))}
            required
          />
          <TextField
            label={`${t("finance.amount")} (${unitLabel})`}
            value={amount}
            inputMode="numeric"
            dir="auto"
            onChange={(event) => setAmount(normalizeDigits(event.target.value))}
            required
          />
          <SelectField
            label={t("finance.refund.method")}
            value={method}
            onChange={setMethod}
            options={[
              { value: "", label: t("finance.refund.useOriginal") },
              { value: "CASH", label: t("finance.methodCash") },
              { value: "POS", label: t("finance.methodPos") },
              { value: "TRANSFER", label: t("finance.methodTransfer") },
            ]}
            helper={t("finance.refund.defaultMethodHint")}
          />
          <p className="muted">
            {t("finance.refund.originalMethod")}:{" "}
            {methodLabel(t, originalMethod)}
            {selectedInvoice ? ` · ${money(selectedInvoice.paid_irr)}` : ""}
          </p>
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
    </>
  )
}
