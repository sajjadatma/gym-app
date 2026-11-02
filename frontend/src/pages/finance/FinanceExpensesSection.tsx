import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, ReceiptText } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type FinanceExpensePublic, FinanceService } from "@/client"
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
import { useSnackbar } from "@/snackbar"
import {
  addDaysIso,
  type FinanceSectionProps,
  methodLabel,
  newKey,
  todayIso,
  useMoney,
} from "./shared"

export function FinanceExpensesSection({
  settings,
  unit,
}: FinanceSectionProps) {
  const { t, formatDate, normalizeDigits } = useI18n()
  const { activeGymId } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, parse, unitLabel } = useMoney(unit)
  const canManage = settings.permissions.includes("finance.expense.manage")

  const [open, setOpen] = useState(false)
  const [category, setCategory] = useState("")
  const [counterparty, setCounterparty] = useState("")
  const [description, setDescription] = useState("")
  const [amount, setAmount] = useState("")
  const [spentOn, setSpentOn] = useState(todayIso)
  const [paid, setPaid] = useState(false)
  const [method, setMethod] = useState("CASH")
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [payTarget, setPayTarget] = useState<FinanceExpensePublic | null>(null)
  const [paidOn, setPaidOn] = useState(todayIso)
  const [payMethod, setPayMethod] = useState("CASH")

  const scope = activeGymId ?? ""
  const expensesQuery = useQuery({
    queryKey: ["finance", scope, "expenses"],
    queryFn: async () =>
      (
        await FinanceService.readFinanceExpenses({
          query: { limit: 50 },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["finance", scope] })
  }

  function openCreate() {
    setCategory("")
    setCounterparty("")
    setDescription("")
    setAmount("")
    setSpentOn(todayIso())
    setPaid(false)
    setMethod("CASH")
    setFormError(null)
    setOpen(true)
  }

  async function submit() {
    const amountIrr = parse(amount)
    if (!category.trim() || amountIrr === null || amountIrr <= 0) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      await FinanceService.createFinanceExpense({
        body: {
          category: category.trim(),
          counterparty: counterparty.trim() || null,
          description: description.trim() || null,
          amount_irr: amountIrr,
          spent_on: spentOn,
          paid,
          method: paid ? (method as "CASH" | "POS" | "TRANSFER") : null,
          recurrence_key: null,
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setOpen(false)
      show(t("finance.expense.created"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function pay() {
    if (!payTarget) return
    setSaving(true)
    try {
      await FinanceService.payFinanceExpense({
        path: { expense_id: payTarget.id },
        body: {
          paid_on: paidOn,
          method: payMethod as "CASH" | "POS" | "TRANSFER",
        },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setPayTarget(null)
      show(t("finance.expense.paidDone"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function repeat(expense: FinanceExpensePublic) {
    setSaving(true)
    try {
      await FinanceService.repeatFinanceExpense({
        path: { expense_id: expense.id },
        body: { spent_on: addDaysIso(expense.spent_on, 30) },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      show(t("finance.expense.repeated"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  const expenses = expensesQuery.data?.data ?? []

  return (
    <>
      <SectionCard
        title={t("finance.expense.title")}
        subtitle={t("finance.expense.subtitle")}
        actions={
          canManage ? (
            <Button icon={<Plus size={16} />} onClick={openCreate}>
              {t("finance.expense.new")}
            </Button>
          ) : null
        }
      >
        {expensesQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : expensesQuery.isError ? (
          <ErrorState
            message={translateApiError(expensesQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => expensesQuery.refetch()}
          />
        ) : expenses.length === 0 ? (
          <EmptyState
            icon={<ReceiptText size={24} />}
            title={t("finance.expense.empty")}
          />
        ) : (
          <div className="stack">
            {expenses.map((expense) => (
              <Card key={expense.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>{expense.category}</strong>
                    <div className="m3-entity-card__meta">
                      <span>
                        {expense.status === "PAID"
                          ? t("finance.expense.paid")
                          : t("finance.expense.unpaid")}
                      </span>
                      <span>{formatDate(expense.spent_on)}</span>
                      {expense.counterparty ? (
                        <span>{expense.counterparty}</span>
                      ) : null}
                      {expense.method ? (
                        <span>{methodLabel(t, expense.method)}</span>
                      ) : null}
                    </div>
                    {expense.description ? (
                      <p className="muted">{expense.description}</p>
                    ) : null}
                  </div>
                  <div style={{ textAlign: "end" }}>
                    <div>{money(expense.amount_irr)}</div>
                    {canManage && expense.status === "UNPAID" ? (
                      <div
                        className="row"
                        style={{ gap: 8, justifyContent: "end" }}
                      >
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => {
                            setPaidOn(expense.spent_on)
                            setPayMethod("CASH")
                            setPayTarget(expense)
                          }}
                        >
                          {t("finance.expense.pay")}
                        </Button>
                        <Button
                          variant="text"
                          size="sm"
                          disabled={saving}
                          onClick={() => void repeat(expense)}
                        >
                          {t("finance.expense.repeat")}
                        </Button>
                      </div>
                    ) : null}
                    {canManage && expense.status === "PAID" ? (
                      <Button
                        variant="text"
                        size="sm"
                        disabled={saving}
                        onClick={() => void repeat(expense)}
                      >
                        {t("finance.expense.repeat")}
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
        title={t("finance.expense.new")}
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
          <TextField
            label={t("finance.expense.category")}
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            required
          />
          <TextField
            label={t("finance.expense.counterparty")}
            value={counterparty}
            onChange={(event) => setCounterparty(event.target.value)}
          />
          <TextField
            label={t("finance.description")}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            multiline
            rows={2}
          />
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
            <DateField
              label={t("finance.expense.spentOn")}
              value={spentOn}
              onChange={(value) => setSpentOn(value ?? todayIso())}
              required
            />
          </div>
          <Switch
            label={t("finance.expense.paid")}
            checked={paid}
            onChange={setPaid}
          />
          {paid ? (
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
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={payTarget !== null}
        title={t("finance.expense.pay")}
        description={payTarget?.category}
        onClose={() => setPayTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setPayTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void pay()}>
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <DateField
            label={t("finance.expense.spentOn")}
            value={paidOn}
            onChange={(value) => setPaidOn(value ?? todayIso())}
            required
          />
          <SelectField
            label={t("finance.refund.method")}
            value={payMethod}
            onChange={setPayMethod}
            options={[
              { value: "CASH", label: t("finance.methodCash") },
              { value: "POS", label: t("finance.methodPos") },
              { value: "TRANSFER", label: t("finance.methodTransfer") },
            ]}
          />
        </div>
      </Dialog>
    </>
  )
}
