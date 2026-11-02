import { useQuery, useQueryClient } from "@tanstack/react-query"
import { FileText, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type FinanceCatalogItemPublic,
  type FinanceInvoiceCreate,
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
  addDaysIso,
  amountInput,
  type FinanceLineKind,
  type FinanceSectionProps,
  invoiceStatusLabel,
  lineKindLabel,
  newKey,
  todayIso,
  useFinanceCustomers,
  useMoney,
} from "./shared"

type LineRow = {
  key: string
  catalogItemId: string
  kind: FinanceLineKind
  description: string
  quantity: string
  unitPrice: string
  lineDiscount: string
  bundleDiscount: string
  coachUserId: string
}

type InstallmentRow = {
  key: string
  dueDate: string
  amount: string
}

const KINDS: FinanceLineKind[] = [
  "MEMBERSHIP",
  "PROGRAM",
  "SESSION",
  "PACK",
  "PRODUCT",
  "SERVICE",
  "CUSTOM",
]

function emptyLine(): LineRow {
  return {
    key: newKey(),
    catalogItemId: "",
    kind: "CUSTOM",
    description: "",
    quantity: "1",
    unitPrice: "",
    lineDiscount: "",
    bundleDiscount: "",
    coachUserId: "",
  }
}

export function FinanceInvoicesSection({
  settings,
  unit,
}: FinanceSectionProps) {
  const { t, formatNumber, formatDate, normalizeDigits } = useI18n()
  const { activeGymId } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, parse } = useMoney(unit)
  const customers = useFinanceCustomers()
  const { coachOptions, customerOptions, customerName } = customers

  const [statusFilter, setStatusFilter] = useState("")
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [customerId, setCustomerId] = useState("")
  const [acquisitionSource, setAcquisitionSource] = useState("GYM")
  const [discountFunding, setDiscountFunding] = useState("GYM")
  const [description, setDescription] = useState("")
  const [dueDate, setDueDate] = useState<string | null>(null)
  const [discount, setDiscount] = useState("")
  const [lines, setLines] = useState<LineRow[]>([emptyLine()])
  const [installments, setInstallments] = useState<InstallmentRow[]>([])
  const [splitCount, setSplitCount] = useState("2")
  const [splitFirst, setSplitFirst] = useState(todayIso)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [issueTarget, setIssueTarget] = useState<FinanceInvoicePublic | null>(
    null,
  )
  const [issueDate, setIssueDate] = useState(todayIso)
  const [voidTarget, setVoidTarget] = useState<FinanceInvoicePublic | null>(
    null,
  )
  const [voidReason, setVoidReason] = useState("")
  const [voidDate, setVoidDate] = useState(todayIso)
  const [discardTarget, setDiscardTarget] =
    useState<FinanceInvoicePublic | null>(null)

  const canManage = settings.permissions.includes("finance.invoice.manage")
  const scope = activeGymId ?? ""

  const invoicesQuery = useQuery({
    queryKey: ["finance", scope, "invoices", statusFilter],
    queryFn: async () =>
      (
        await FinanceService.readFinanceInvoices({
          query: {
            limit: 50,
            status: statusFilter || undefined,
          },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })
  const catalogQuery = useQuery({
    queryKey: ["finance", scope, "catalog", "active"],
    queryFn: async () =>
      (
        await FinanceService.readFinanceCatalog({
          query: { active_only: true },
        })
      ).data.data,
    enabled: Boolean(activeGymId),
  })

  const catalog = catalogQuery.data ?? []
  const invoices = invoicesQuery.data?.data ?? []

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["finance", scope] })
  }

  function resetForm() {
    setEditingId(null)
    setCustomerId("")
    setAcquisitionSource("GYM")
    setDiscountFunding("GYM")
    setDescription("")
    setDueDate(null)
    setDiscount("")
    setLines([emptyLine()])
    setInstallments([])
    setSplitCount("2")
    setSplitFirst(todayIso())
    setFormError(null)
  }

  function openCreate() {
    resetForm()
    setFormOpen(true)
  }

  function openEdit(invoice: FinanceInvoicePublic) {
    setEditingId(invoice.id)
    setCustomerId(invoice.customer_user_id)
    setAcquisitionSource(invoice.acquisition_source ?? "GYM")
    setDiscountFunding(invoice.discount_funding ?? "GYM")
    setDescription(invoice.description ?? "")
    setDueDate(invoice.due_date ?? null)
    setDiscount(
      invoice.discount_irr ? amountInput(invoice.discount_irr, unit) : "",
    )
    setLines(
      invoice.lines.map((line) => ({
        key: newKey(),
        catalogItemId: line.catalog_item_id ?? "",
        kind: line.kind,
        description: line.description,
        quantity: String(line.quantity),
        unitPrice: amountInput(line.unit_price_irr, unit),
        lineDiscount: line.line_discount_irr
          ? amountInput(line.line_discount_irr, unit)
          : "",
        bundleDiscount:
          invoice.discount_irr > 0
            ? amountInput(line.discount_share_irr, unit)
            : "",
        coachUserId: line.coach_user_id ?? "",
      })),
    )
    setInstallments(
      invoice.installments.map((item) => ({
        key: newKey(),
        dueDate: item.due_date,
        amount: amountInput(item.amount_irr, unit),
      })),
    )
    setFormError(null)
    setFormOpen(true)
  }

  function updateLine(key: string, patch: Partial<LineRow>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    )
  }

  function chooseCatalogItem(key: string, itemId: string) {
    const item = catalog.find(
      (entry: FinanceCatalogItemPublic) => entry.id === itemId,
    )
    updateLine(key, {
      catalogItemId: itemId,
      ...(item
        ? {
            kind: item.kind,
            description: item.name,
            unitPrice: amountInput(item.default_price_irr, unit),
          }
        : {}),
    })
  }

  function lineNet(line: LineRow) {
    const price = parse(line.unitPrice) ?? 0
    const quantity = Number(normalizeDigits(line.quantity)) || 0
    const lineDiscount = parse(line.lineDiscount) ?? 0
    return Math.max(price * quantity - lineDiscount, 0)
  }

  function subtotal() {
    return lines.reduce((total, line) => total + lineNet(line), 0)
  }

  function total() {
    return Math.max(subtotal() - (parse(discount) ?? 0), 0)
  }

  function generateInstallments() {
    const count = Math.max(
      1,
      Math.min(36, Number(normalizeDigits(splitCount)) || 1),
    )
    const amount = total()
    if (amount <= 0) {
      setFormError(t("finance.invoice.totalRequired"))
      return
    }
    const base = Math.floor(amount / count)
    const rows: InstallmentRow[] = []
    let allocated = 0
    for (let index = 0; index < count; index += 1) {
      const value = index === count - 1 ? amount - allocated : base
      allocated += value
      rows.push({
        key: newKey(),
        dueDate: addDaysIso(splitFirst || todayIso(), index * 30),
        amount: amountInput(value, unit),
      })
    }
    setInstallments(rows)
    setFormError(null)
  }

  function buildBody(): FinanceInvoiceCreate | null {
    if (!customerId) {
      setFormError(t("finance.chooseCustomer"))
      return null
    }
    const explicitBundle = lines.some((line) => line.bundleDiscount.trim())
    const parsedLines = lines.map((line) => {
      const price = parse(line.unitPrice)
      const quantity = Number(normalizeDigits(line.quantity))
      const lineDiscount = line.lineDiscount ? parse(line.lineDiscount) : 0
      const bundleDiscount = line.bundleDiscount
        ? parse(line.bundleDiscount)
        : explicitBundle
          ? null
          : 0
      if (
        !line.description.trim() ||
        price === null ||
        !Number.isSafeInteger(quantity) ||
        quantity < 1 ||
        lineDiscount === null ||
        bundleDiscount === null
      ) {
        return null
      }
      return {
        catalog_item_id: line.catalogItemId || null,
        kind: line.kind,
        description: line.description.trim(),
        quantity,
        unit_price_irr: price,
        line_discount_irr: lineDiscount,
        bundle_discount_irr: explicitBundle ? bundleDiscount : null,
        coach_user_id: line.coachUserId || null,
      }
    })
    if (parsedLines.some((line) => line === null)) {
      setFormError(t("finance.invalidAmount"))
      return null
    }
    const discountIrr = discount ? parse(discount) : 0
    if (discountIrr === null) {
      setFormError(t("finance.invalidAmount"))
      return null
    }
    const parsedInstallments = installments.map((item) => ({
      due_date: item.dueDate,
      amount_irr: parse(item.amount),
    }))
    if (parsedInstallments.some((item) => item.amount_irr === null)) {
      setFormError(t("finance.invalidAmount"))
      return null
    }
    if (parsedInstallments.length > 0) {
      const sum = parsedInstallments.reduce(
        (value, item) => value + (item.amount_irr ?? 0),
        0,
      )
      if (sum !== total()) {
        setFormError(t("errors.finance_installments_mismatch"))
        return null
      }
    }
    return {
      customer_user_id: customerId,
      acquisition_source: acquisitionSource as "GYM" | "ASCORA",
      discount_funding: discountFunding as "GYM" | "COACH" | "ASCORA" | "MIXED",
      description: description.trim() || null,
      due_date: dueDate,
      discount_irr: discountIrr,
      lines: parsedLines as FinanceInvoiceCreate["lines"],
      installments:
        parsedInstallments.length > 0
          ? (parsedInstallments as FinanceInvoiceCreate["installments"])
          : null,
    }
  }

  async function submit() {
    const body = buildBody()
    if (!body) return
    setSaving(true)
    setFormError(null)
    try {
      if (editingId) {
        await FinanceService.updateFinanceInvoice({
          path: { invoice_id: editingId },
          body,
        })
      } else {
        await FinanceService.createFinanceInvoice({ body })
      }
      await invalidate()
      setFormOpen(false)
      resetForm()
      show(t("finance.invoice.created"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function issue() {
    if (!issueTarget) return
    setSaving(true)
    try {
      await FinanceService.issueFinanceInvoice({
        path: { invoice_id: issueTarget.id },
        body: { posting_date: issueDate },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setIssueTarget(null)
      show(t("finance.invoice.issuedDone"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function voidInvoice() {
    if (!voidTarget) return
    setSaving(true)
    try {
      await FinanceService.voidFinanceInvoice({
        path: { invoice_id: voidTarget.id },
        body: { reason: voidReason.trim(), posting_date: voidDate },
        headers: { "Idempotency-Key": newKey() },
      })
      await invalidate()
      setVoidTarget(null)
      setVoidReason("")
      show(t("finance.invoice.voidedDone"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function discard() {
    if (!discardTarget) return
    setSaving(true)
    try {
      await FinanceService.deleteFinanceInvoice({
        path: { invoice_id: discardTarget.id },
      })
      await invalidate()
      setDiscardTarget(null)
      show(t("finance.invoice.discarded"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <SectionCard
        title={t("finance.invoice.title")}
        subtitle={t("finance.subtitle")}
        actions={
          canManage ? (
            <Button icon={<Plus size={16} />} onClick={openCreate}>
              {t("finance.invoice.new")}
            </Button>
          ) : null
        }
      >
        <SelectField
          label={t("finance.invoice.status")}
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            { value: "", label: t("finance.allStatuses") },
            { value: "DRAFT", label: t("finance.invoice.draft") },
            { value: "ISSUED", label: t("finance.invoice.issued") },
            { value: "VOID", label: t("finance.invoice.void") },
          ]}
        />
        {invoicesQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : invoicesQuery.isError ? (
          <ErrorState
            message={translateApiError(invoicesQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => invoicesQuery.refetch()}
          />
        ) : invoices.length === 0 ? (
          <EmptyState
            icon={<FileText size={24} />}
            title={t("finance.invoice.empty")}
          />
        ) : (
          <div className="stack">
            {invoices.map((invoice) => (
              <Card key={invoice.id} variant="outlined">
                <div className="row row--between" style={{ gap: 12 }}>
                  <div>
                    <strong>
                      {invoice.invoice_number
                        ? t("finance.invoice.number") +
                          " " +
                          formatNumber(invoice.invoice_number)
                        : t("finance.invoice.draft")}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>
                        {invoice.customer_name ??
                          customerName(invoice.customer_user_id)}
                      </span>
                      <span
                        className={`m3-status m3-status--${invoice.status.toLowerCase()}`}
                      >
                        {invoiceStatusLabel(t, invoice.status)}
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
                    {invoice.description ? (
                      <p className="muted">{invoice.description}</p>
                    ) : null}
                    <div className="m3-entity-card__meta">
                      <span>
                        {t("finance.invoice.total")}: {money(invoice.total_irr)}
                      </span>
                      <span>
                        {t("finance.invoice.paid")}: {money(invoice.paid_irr)}
                      </span>
                      <span>
                        {t("finance.invoice.balance")}:{" "}
                        {money(invoice.balance_irr)}
                      </span>
                      <span>
                        {t("finance.invoice.source")}:{" "}
                        {invoice.acquisition_source === "ASCORA"
                          ? t("finance.invoice.sourceAscora")
                          : t("finance.invoice.sourceGym")}
                      </span>
                      <span>
                        {t("finance.invoice.discountFunding")}:{" "}
                        {invoice.discount_funding === "COACH"
                          ? t("finance.invoice.fundingCoach")
                          : invoice.discount_funding === "ASCORA"
                            ? t("finance.invoice.fundingAscora")
                            : invoice.discount_funding === "MIXED"
                              ? t("finance.invoice.fundingMixed")
                              : t("finance.invoice.fundingGym")}
                      </span>
                    </div>
                  </div>
                  <div className="row" style={{ gap: 8 }}>
                    {canManage && invoice.status === "DRAFT" ? (
                      <>
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => openEdit(invoice)}
                        >
                          {t("finance.invoice.edit")}
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => {
                            setIssueDate(todayIso())
                            setIssueTarget(invoice)
                          }}
                        >
                          {t("finance.invoice.issue")}
                        </Button>
                        <Button
                          variant="text"
                          size="sm"
                          icon={<Trash2 size={15} />}
                          aria-label={t("finance.invoice.discard")}
                          onClick={() => setDiscardTarget(invoice)}
                        />
                      </>
                    ) : null}
                    {canManage && invoice.status === "ISSUED" ? (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() => {
                          setVoidReason("")
                          setVoidDate(todayIso())
                          setVoidTarget(invoice)
                        }}
                      >
                        {t("finance.invoice.voidAction")}
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
                        <th>{t("finance.unitPrice")}</th>
                        <th>{t("finance.lineDiscount")}</th>
                        <th>{t("finance.invoice.total")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoice.lines.map((line) => (
                        <tr key={line.id}>
                          <td>
                            {line.description}
                            <div className="muted">
                              {lineKindLabel(t, line.kind)}
                            </div>
                          </td>
                          <td>{formatNumber(line.quantity)}</td>
                          <td>{money(line.unit_price_irr)}</td>
                          <td>{money(line.line_discount_irr)}</td>
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
                          <th>#</th>
                          <th>{t("finance.invoice.dueDate")}</th>
                          <th>{t("finance.amount")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {invoice.installments.map((item) => (
                          <tr key={item.id}>
                            <td>{formatNumber(item.sequence)}</td>
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

      <Dialog
        open={formOpen}
        title={editingId ? t("finance.invoice.edit") : t("finance.invoice.new")}
        description={t("finance.invoice.lines")}
        onClose={() => setFormOpen(false)}
        size="lg"
        footer={
          <>
            <Button variant="text" onClick={() => setFormOpen(false)}>
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
            onChange={setCustomerId}
            options={customerOptions}
            placeholder={t("finance.chooseCustomer")}
            required
          />
          <div className="row" style={{ gap: 12 }}>
            <SelectField
              label={t("finance.invoice.source")}
              value={acquisitionSource}
              onChange={setAcquisitionSource}
              options={[
                { value: "GYM", label: t("finance.invoice.sourceGym") },
                { value: "ASCORA", label: t("finance.invoice.sourceAscora") },
              ]}
              containerClassName="grow"
            />
            <SelectField
              label={t("finance.invoice.discountFunding")}
              value={discountFunding}
              onChange={setDiscountFunding}
              options={[
                { value: "GYM", label: t("finance.invoice.fundingGym") },
                { value: "COACH", label: t("finance.invoice.fundingCoach") },
                {
                  value: "ASCORA",
                  label: t("finance.invoice.fundingAscora"),
                },
                { value: "MIXED", label: t("finance.invoice.fundingMixed") },
              ]}
              containerClassName="grow"
            />
          </div>
          <TextField
            label={t("finance.description")}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            multiline
            rows={2}
          />
          <DateField
            label={t("finance.invoice.dueDate")}
            value={dueDate}
            onChange={setDueDate}
          />

          <h3 className="m3-section__subtitle">{t("finance.invoice.lines")}</h3>
          {lines.map((line, index) => (
            <Card key={line.key} variant="plain">
              <div className="stack">
                <SelectField
                  label={t("finance.catalog.title")}
                  value={line.catalogItemId}
                  onChange={(value) => chooseCatalogItem(line.key, value)}
                  options={[
                    { value: "", label: t("finance.invoice.kindCustom") },
                    ...catalog.map((item) => ({
                      value: item.id,
                      label: `${item.name} · ${money(item.default_price_irr)}`,
                    })),
                  ]}
                />
                <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
                  <SelectField
                    label={t("finance.invoice.kind")}
                    value={line.kind}
                    onChange={(value) =>
                      updateLine(line.key, {
                        kind: value as FinanceLineKind,
                      })
                    }
                    options={KINDS.map((kind) => ({
                      value: kind,
                      label: lineKindLabel(t, kind),
                    }))}
                  />
                  <TextField
                    label={t("finance.description")}
                    value={line.description}
                    onChange={(event) =>
                      updateLine(line.key, { description: event.target.value })
                    }
                    containerClassName="grow"
                    required
                  />
                </div>
                <SelectField
                  label={t("finance.invoice.coach")}
                  value={line.coachUserId}
                  onChange={(value) =>
                    updateLine(line.key, { coachUserId: value })
                  }
                  options={[
                    { value: "", label: t("finance.invoice.noCoach") },
                    ...coachOptions,
                  ]}
                  helper={t("finance.invoice.coachHint")}
                />
                <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
                  <TextField
                    label={t("finance.quantity")}
                    value={line.quantity}
                    inputMode="numeric"
                    dir="auto"
                    onChange={(event) =>
                      updateLine(line.key, {
                        quantity: normalizeDigits(event.target.value),
                      })
                    }
                  />
                  <TextField
                    label={t("finance.unitPrice")}
                    value={line.unitPrice}
                    inputMode="decimal"
                    dir="auto"
                    onChange={(event) =>
                      updateLine(line.key, {
                        unitPrice: normalizeDigits(event.target.value),
                      })
                    }
                  />
                  <TextField
                    label={t("finance.lineDiscount")}
                    value={line.lineDiscount}
                    inputMode="decimal"
                    dir="auto"
                    onChange={(event) =>
                      updateLine(line.key, {
                        lineDiscount: normalizeDigits(event.target.value),
                      })
                    }
                  />
                  {total() > 0 || parse(discount) ? (
                    <TextField
                      label={t("finance.invoice.bundleDiscount")}
                      helper={t("finance.invoice.bundleDiscountHint")}
                      value={line.bundleDiscount}
                      inputMode="decimal"
                      dir="auto"
                      onChange={(event) =>
                        updateLine(line.key, {
                          bundleDiscount: normalizeDigits(event.target.value),
                        })
                      }
                    />
                  ) : null}
                  <span className="muted">{money(lineNet(line))}</span>
                  {lines.length > 1 ? (
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
                      setLines((current) => [...current, emptyLine()])
                    }
                  >
                    {t("finance.addLine")}
                  </Button>
                ) : null}
              </div>
            </Card>
          ))}

          <TextField
            label={t("finance.discount")}
            value={discount}
            inputMode="decimal"
            dir="auto"
            onChange={(event) =>
              setDiscount(normalizeDigits(event.target.value))
            }
          />
          <div className="row row--between">
            <span>
              {t("finance.invoice.total")}: {money(total())}
            </span>
          </div>

          <h3 className="m3-section__subtitle">
            {t("finance.invoice.installmentCount")}
          </h3>
          <div className="row" style={{ gap: 8, alignItems: "flex-end" }}>
            <TextField
              label={t("finance.invoice.installmentCount")}
              value={splitCount}
              inputMode="numeric"
              dir="auto"
              onChange={(event) =>
                setSplitCount(normalizeDigits(event.target.value))
              }
            />
            <DateField
              label={t("finance.invoice.dueDate")}
              value={splitFirst}
              onChange={(value) => setSplitFirst(value ?? todayIso())}
            />
            <Button variant="tonal" onClick={generateInstallments}>
              {t("finance.invoice.generateInstallments")}
            </Button>
          </div>
          {installments.map((item, index) => (
            <div
              key={item.key}
              className="row"
              style={{ gap: 8, alignItems: "flex-end" }}
            >
              <DateField
                label={t("finance.invoice.dueDate")}
                value={item.dueDate}
                onChange={(value) =>
                  setInstallments((current) =>
                    current.map((row) =>
                      row.key === item.key
                        ? { ...row, dueDate: value ?? todayIso() }
                        : row,
                    ),
                  )
                }
              />
              <TextField
                label={t("finance.amount")}
                value={item.amount}
                inputMode="decimal"
                dir="auto"
                onChange={(event) =>
                  setInstallments((current) =>
                    current.map((row) =>
                      row.key === item.key
                        ? {
                            ...row,
                            amount: normalizeDigits(event.target.value),
                          }
                        : row,
                    ),
                  )
                }
              />
              {index === installments.length - 1 ? (
                <Button
                  variant="text"
                  aria-label={t("finance.removeLine")}
                  icon={<Trash2 size={16} />}
                  onClick={() =>
                    setInstallments((current) =>
                      current.filter((row) => row.key !== item.key),
                    )
                  }
                />
              ) : null}
            </div>
          ))}
        </div>
      </Dialog>

      <Dialog
        open={issueTarget !== null}
        title={t("finance.invoice.issue")}
        description={
          issueTarget?.customer_name ??
          (issueTarget ? customerName(issueTarget.customer_user_id) : "")
        }
        onClose={() => setIssueTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setIssueTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void issue()}>
              {t("finance.invoice.issue")}
            </Button>
          </>
        }
      >
        <DateField
          label={t("finance.invoice.issueDate")}
          value={issueDate}
          onChange={(value) => setIssueDate(value ?? todayIso())}
          required
        />
      </Dialog>

      <Dialog
        open={voidTarget !== null}
        title={t("finance.invoice.voidAction")}
        description={
          voidTarget?.invoice_number
            ? t("finance.invoice.number") +
              " " +
              formatNumber(voidTarget.invoice_number)
            : undefined
        }
        onClose={() => setVoidTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setVoidTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={voidReason.trim().length < 3}
              onClick={() => void voidInvoice()}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <TextField
            label={t("finance.invoice.voidReason")}
            value={voidReason}
            onChange={(event) => setVoidReason(event.target.value)}
            multiline
            required
          />
          <DateField
            label={t("finance.postingDate")}
            value={voidDate}
            onChange={(value) => setVoidDate(value ?? todayIso())}
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={discardTarget !== null}
        title={t("finance.invoice.discard")}
        description={discardTarget?.customer_name ?? undefined}
        onClose={() => setDiscardTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setDiscardTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              onClick={() => void discard()}
              variant="filled"
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <p className="muted">{t("finance.invoice.discardHint")}</p>
      </Dialog>
    </>
  )
}
