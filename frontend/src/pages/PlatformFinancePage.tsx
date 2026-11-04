import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Landmark, Plus } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import {
  GymsService,
  type PlatformAgreementPublic,
  type PlatformInvoicePublic,
  type PlatformPlanPublic,
  PlatformService,
} from "@/client"
import { DateField } from "@/components/DateField"
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
  Tabs,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

const MODES = [
  { value: "FREE", label: "رایگان" },
  { value: "SUBSCRIPTION", label: "اشتراک" },
  { value: "COMMISSION", label: "کمیسیون" },
  { value: "HYBRID", label: "ترکیبی" },
  { value: "CUSTOM", label: "سفارشی" },
]

function today() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

function monthStart() {
  return `${today().slice(0, 7)}-01`
}

function tomorrow() {
  const now = new Date()
  now.setDate(now.getDate() + 1)
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

async function downloadCsv(path: string) {
  const token = localStorage.getItem("token")
  const response = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) throw new Error("download_failed")
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = path.includes("platform") ? "platform.csv" : "finance.csv"
  anchor.click()
  URL.revokeObjectURL(url)
}

export function PlatformFinancePage() {
  const { t, formatNumber, formatDate, normalizeDigits } = useI18n()
  const { show } = useSnackbar()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState("overview")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [planOpen, setPlanOpen] = useState(false)
  const [versionPlan, setVersionPlan] = useState<PlatformPlanPublic | null>(
    null,
  )
  const [agreementOpen, setAgreementOpen] = useState(false)
  const [groupOpen, setGroupOpen] = useState(false)
  const [costOpen, setCostOpen] = useState(false)
  const [invoiceOpen, setInvoiceOpen] = useState(false)
  const [cancelTarget, setCancelTarget] =
    useState<PlatformInvoicePublic | null>(null)
  const [paymentTarget, setPaymentTarget] =
    useState<PlatformInvoicePublic | null>(null)
  const [planForm, setPlanForm] = useState({
    code: "",
    name: "",
    price: "0",
  })
  const [versionForm, setVersionForm] = useState({
    effective_from: today(),
    price: "0",
  })
  const [agreementForm, setAgreementForm] = useState({
    gym_id: "",
    group_id: "",
    mode: "COMMISSION",
    amount: "0",
    percent: "10",
    effective_from: today(),
  })
  const [groupForm, setGroupForm] = useState({
    name: "",
    gym_id: "",
  })
  const [costForm, setCostForm] = useState({
    category: "",
    amount: "0",
    gym_id: "",
    incurred_on: today(),
  })
  const [invoiceForm, setInvoiceForm] = useState({ gym_id: "" })
  const [paymentAmount, setPaymentAmount] = useState("")
  const [cancelReason, setCancelReason] = useState("")

  const fromDate = monthStart()
  const toDate = today()
  const gymsQuery = useQuery({
    queryKey: ["platform", "gyms"],
    queryFn: async () => (await GymsService.listGyms()).data.data,
  })
  const overviewQuery = useQuery({
    queryKey: ["platform", "overview", fromDate, toDate],
    queryFn: async () =>
      (
        await PlatformService.readPlatformOverview({
          query: { from_date: fromDate, to_date: toDate },
        })
      ).data,
  })
  const plansQuery = useQuery({
    queryKey: ["platform", "plans"],
    queryFn: async () => (await PlatformService.readPlatformPlans()).data.data,
  })
  const agreementsQuery = useQuery({
    queryKey: ["platform", "agreements"],
    queryFn: async () =>
      (await PlatformService.readPlatformAgreements()).data.data,
  })
  const groupsQuery = useQuery({
    queryKey: ["platform", "groups"],
    queryFn: async () => (await PlatformService.readPlatformGroups()).data.data,
  })
  const invoicesQuery = useQuery({
    queryKey: ["platform", "invoices"],
    queryFn: async () =>
      (await PlatformService.readPlatformInvoices()).data.data,
  })
  const duesQuery = useQuery({
    queryKey: ["platform", "dues"],
    queryFn: async () => (await PlatformService.readPlatformDues()).data,
  })
  const remindersQuery = useQuery({
    queryKey: ["platform", "reminders"],
    queryFn: async () => (await PlatformService.readPlatformReminders()).data,
  })

  const gyms = gymsQuery.data ?? []
  const gymOptions = gyms.map((gym) => ({
    value: gym.id,
    label: gym.name,
  }))

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["platform"] })
  }

  async function createPlan() {
    setSaving(true)
    setError("")
    try {
      await PlatformService.createPlatformPlan({
        body: {
          code: planForm.code,
          name: planForm.name,
          version: {
            effective_from: today(),
            monthly_price_irr: Number(normalizeDigits(planForm.price)) || 0,
            limits: {},
          },
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setPlanOpen(false)
      show(t("platform.saved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function createAgreement() {
    setSaving(true)
    setError("")
    try {
      const terms =
        agreementForm.mode === "FREE" || agreementForm.mode === "SUBSCRIPTION"
          ? []
          : [
              {
                kind: "ANY",
                acquisition_source: "ANY",
                basis: "PERCENT" as const,
                percent_bp: Math.round(
                  Number(normalizeDigits(agreementForm.percent)) * 100,
                ),
              },
            ]
      await PlatformService.createPlatformAgreement({
        body: {
          gym_id: agreementForm.group_id ? null : agreementForm.gym_id,
          group_id: agreementForm.group_id || null,
          mode: agreementForm.mode as
            | "FREE"
            | "SUBSCRIPTION"
            | "COMMISSION"
            | "HYBRID"
            | "CUSTOM",
          effective_from: agreementForm.effective_from,
          subscription_amount_irr:
            Number(normalizeDigits(agreementForm.amount)) || 0,
          terms,
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setAgreementOpen(false)
      show(t("platform.saved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function activateAgreement(id: string) {
    setSaving(true)
    try {
      await PlatformService.activatePlatformAgreement({
        path: { agreement_id: id },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      show(t("platform.activated"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function issueInvoice() {
    setSaving(true)
    setError("")
    try {
      await PlatformService.issuePlatformInvoice({
        body: {
          gym_id: invoiceForm.gym_id,
          period_start: monthStart(),
          period_end: today(),
          due_on: today(),
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setInvoiceOpen(false)
      show(t("platform.saved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function recordPayment() {
    if (!paymentTarget) return
    setSaving(true)
    setError("")
    try {
      await PlatformService.recordPlatformInvoicePayment({
        path: { invoice_id: paymentTarget.id },
        body: {
          amount_irr: Number(normalizeDigits(paymentAmount)) || 0,
          method: "TRANSFER",
          received_on: today(),
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setPaymentTarget(null)
      setPaymentAmount("")
      show(t("platform.saved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function cancelInvoice(invoice: PlatformInvoicePublic) {
    if (cancelReason.trim().length < 3) return
    setSaving(true)
    try {
      await PlatformService.cancelPlatformInvoice({
        path: { invoice_id: invoice.id },
        body: { reason: cancelReason.trim() },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setCancelTarget(null)
      setCancelReason("")
      show(t("platform.saved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function createVersion() {
    if (!versionPlan) return
    setSaving(true)
    try {
      await PlatformService.createPlatformPlanVersion({
        path: { plan_id: versionPlan.id },
        body: {
          effective_from: versionForm.effective_from,
          monthly_price_irr: Number(normalizeDigits(versionForm.price)) || 0,
          limits: {},
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setVersionPlan(null)
      show(t("platform.saved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function createGroup() {
    if (!groupForm.name.trim() || !groupForm.gym_id) return
    setSaving(true)
    try {
      await PlatformService.createPlatformGroup({
        body: {
          name: groupForm.name,
          members: [{ gym_id: groupForm.gym_id, allocation_bp: 10000 }],
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setGroupOpen(false)
      show(t("platform.saved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function createCost() {
    setSaving(true)
    try {
      await PlatformService.createPlatformCost({
        body: {
          gym_id: costForm.gym_id || null,
          category: costForm.category,
          amount_irr: Number(normalizeDigits(costForm.amount)) || 0,
          incurred_on: costForm.incurred_on,
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      })
      await invalidate()
      setCostOpen(false)
      show(t("platform.saved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  async function setVersionStatus(
    plan: PlatformPlanPublic,
    versionId: string,
    action: "activate" | "retire",
  ) {
    setSaving(true)
    try {
      if (action === "activate") {
        await PlatformService.activatePlatformPlanVersion({
          path: { plan_id: plan.id, version_id: versionId },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        })
      } else {
        await PlatformService.retirePlatformPlanVersion({
          path: { plan_id: plan.id, version_id: versionId },
          headers: { "Idempotency-Key": crypto.randomUUID() },
        })
      }
      await invalidate()
      show(t("platform.saved"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t("platform.title")}
        subtitle={t("platform.subtitle")}
        actions={
          <div className="row" style={{ gap: 8 }}>
            <Button variant="text" onClick={() => setCostOpen(true)}>
              {t("platform.newCost")}
            </Button>
            <Button
              variant="tonal"
              onClick={() =>
                void downloadCsv(
                  `/api/v1/platform/reports/export?from_date=${fromDate}&to_date=${toDate}`,
                )
              }
            >
              {t("platform.export")}
            </Button>
          </div>
        }
      />
      <Tabs
        value={tab}
        onChange={setTab}
        idPrefix="platform-tabs"
        tabs={[
          { value: "overview", label: t("platform.overview") },
          { value: "plans", label: t("platform.plans") },
          { value: "agreements", label: t("platform.agreements") },
          { value: "invoices", label: t("platform.invoices") },
          { value: "dues", label: t("platform.dues") },
        ]}
      />
      <div style={{ paddingTop: 16 }}>
        {tab === "overview" ? (
          overviewQuery.isLoading ? (
            <Spinner label={t("common.loading")} />
          ) : overviewQuery.isError ? (
            <ErrorState
              message={translateApiError(overviewQuery.error, t)}
              retryLabel={t("common.retry")}
              onRetry={() => void overviewQuery.refetch()}
            />
          ) : overviewQuery.data ? (
            <div className="stack">
              {overviewQuery.data.zero_plan_mode ? (
                <div className="m3-inline-alert" role="status">
                  {t("platform.zeroPlanMode")}
                </div>
              ) : null}
              <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
                <Card variant="outlined">
                  <strong>{t("platform.mrr")}</strong>
                  <div>{formatNumber(overviewQuery.data.mrr_irr)}</div>
                </Card>
                <Card variant="outlined">
                  <strong>{t("platform.collected")}</strong>
                  <div>
                    {formatNumber(overviewQuery.data.collected_fees_irr)}
                  </div>
                </Card>
                <Card variant="outlined">
                  <strong>{t("platform.recognized")}</strong>
                  <div>
                    {formatNumber(
                      overviewQuery.data.recognized_platform_revenue_irr,
                    )}
                  </div>
                </Card>
                <Card variant="outlined">
                  <strong>{t("platform.receivable")}</strong>
                  <div>{formatNumber(overviewQuery.data.receivable_irr)}</div>
                </Card>
                <Card variant="outlined">
                  <strong>{t("platform.profit")}</strong>
                  <div>
                    {formatNumber(
                      overviewQuery.data.estimated_operating_profit_irr,
                    )}
                  </div>
                </Card>
              </div>
              <SectionCard title={t("platform.byGym")}>
                {overviewQuery.data.by_gym.length === 0 ? (
                  <EmptyState
                    icon={<Landmark size={24} />}
                    title={t("platform.empty")}
                  />
                ) : (
                  <div className="stack">
                    {overviewQuery.data.by_gym.map((row) => (
                      <div className="row row--between" key={row.gym_id}>
                        <span>{row.gym_id}</span>
                        <span>
                          {t("platform.contribution")}:{" "}
                          {formatNumber(row.contribution_irr)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </SectionCard>
            </div>
          ) : null
        ) : null}

        {tab === "plans" ? (
          <SectionCard
            title={t("platform.plans")}
            actions={
              <Button
                icon={<Plus size={16} />}
                onClick={() => setPlanOpen(true)}
              >
                {t("platform.newPlan")}
              </Button>
            }
          >
            {plansQuery.isLoading ? (
              <Spinner label={t("common.loading")} />
            ) : (plansQuery.data ?? []).length === 0 ? (
              <EmptyState
                icon={<Landmark size={24} />}
                title={t("platform.noPlans")}
              />
            ) : (
              <div className="stack">
                {(plansQuery.data ?? []).map((plan: PlatformPlanPublic) => (
                  <Card variant="outlined" key={plan.id}>
                    <div className="row row--between">
                      <div>
                        <strong>{plan.name}</strong>
                        <div className="muted">{plan.code}</div>
                      </div>
                      <div className="row" style={{ gap: 8 }}>
                        {plan.versions.map((version) => (
                          <div
                            className="row"
                            style={{ gap: 4 }}
                            key={version.id}
                          >
                            <span className="m3-chip">
                              v{version.version_number} {version.status} ·{" "}
                              {formatNumber(version.monthly_price_irr)}
                            </span>
                            {version.status === "DRAFT" ? (
                              <Button
                                size="sm"
                                onClick={() =>
                                  void setVersionStatus(
                                    plan,
                                    version.id,
                                    "activate",
                                  )
                                }
                              >
                                {t("platform.activate")}
                              </Button>
                            ) : null}
                            {version.status === "ACTIVE" ? (
                              <Button
                                size="sm"
                                variant="text"
                                onClick={() =>
                                  void setVersionStatus(
                                    plan,
                                    version.id,
                                    "retire",
                                  )
                                }
                              >
                                {t("platform.retire")}
                              </Button>
                            ) : null}
                          </div>
                        ))}
                        <Button
                          size="sm"
                          variant="text"
                          onClick={() => {
                            setVersionForm({
                              effective_from: tomorrow(),
                              price: "0",
                            })
                            setVersionPlan(plan)
                          }}
                        >
                          {t("platform.newVersion")}
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </SectionCard>
        ) : null}

        {tab === "agreements" ? (
          <SectionCard
            title={t("platform.agreements")}
            actions={
              <div className="row" style={{ gap: 8 }}>
                <Button variant="text" onClick={() => setGroupOpen(true)}>
                  {t("platform.newGroup")}
                </Button>
                <Button
                  icon={<Plus size={16} />}
                  onClick={() => setAgreementOpen(true)}
                >
                  {t("platform.newAgreement")}
                </Button>
              </div>
            }
          >
            {agreementsQuery.isLoading ? (
              <Spinner label={t("common.loading")} />
            ) : (agreementsQuery.data ?? []).length === 0 ? (
              <EmptyState
                icon={<Landmark size={24} />}
                title={t("platform.empty")}
              />
            ) : (
              <div className="stack">
                {(agreementsQuery.data ?? []).map(
                  (agreement: PlatformAgreementPublic) => (
                    <Card variant="outlined" key={agreement.id}>
                      <div className="row row--between">
                        <div>
                          <strong>
                            {agreement.mode} · v{agreement.version}
                          </strong>
                          <div className="muted">
                            {agreement.gym_id ?? agreement.group_id} ·{" "}
                            {formatDate(agreement.effective_from)}
                          </div>
                        </div>
                        <div className="row" style={{ gap: 8 }}>
                          <span className="m3-chip">{agreement.status}</span>
                          {agreement.status === "DRAFT" ? (
                            <Button
                              size="sm"
                              loading={saving}
                              onClick={() =>
                                void activateAgreement(agreement.id)
                              }
                            >
                              {t("platform.activate")}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </Card>
                  ),
                )}
              </div>
            )}
          </SectionCard>
        ) : null}

        {tab === "invoices" ? (
          <SectionCard
            title={t("platform.invoices")}
            actions={
              <Button
                icon={<Plus size={16} />}
                onClick={() => setInvoiceOpen(true)}
              >
                {t("platform.newInvoice")}
              </Button>
            }
          >
            {invoicesQuery.isLoading ? (
              <Spinner label={t("common.loading")} />
            ) : (invoicesQuery.data ?? []).length === 0 ? (
              <EmptyState
                icon={<Landmark size={24} />}
                title={t("platform.empty")}
              />
            ) : (
              <div className="stack">
                {(invoicesQuery.data ?? []).map(
                  (invoice: PlatformInvoicePublic) => (
                    <Card variant="outlined" key={invoice.id}>
                      <div className="row row--between">
                        <div>
                          <strong>
                            #{formatNumber(invoice.invoice_number)}
                          </strong>
                          <div className="muted">
                            {invoice.status} · {formatNumber(invoice.total_irr)}{" "}
                            · {formatNumber(invoice.balance_irr)}
                          </div>
                        </div>
                        <div className="stack" style={{ marginTop: 8 }}>
                          {invoice.lines.map((line) => (
                            <div className="muted" key={line.id}>
                              {line.description} ·{" "}
                              {formatNumber(line.amount_irr)} ·{" "}
                              {t("platform.paid")}:{" "}
                              {formatNumber(line.paid_irr)} ·{" "}
                              {t("platform.balance")}:{" "}
                              {formatNumber(line.balance_irr)}
                            </div>
                          ))}
                        </div>
                        <div className="row" style={{ gap: 8 }}>
                          {invoice.status !== "CANCELLED" &&
                          invoice.balance_irr > 0 ? (
                            <Button
                              size="sm"
                              onClick={() => {
                                setPaymentAmount(String(invoice.balance_irr))
                                setPaymentTarget(invoice)
                              }}
                            >
                              {t("platform.pay")}
                            </Button>
                          ) : null}
                          {invoice.status === "ISSUED" ? (
                            <Button
                              size="sm"
                              variant="text"
                              loading={saving}
                              onClick={() => {
                                setCancelReason("")
                                setCancelTarget(invoice)
                              }}
                            >
                              {t("platform.cancelInvoice")}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </Card>
                  ),
                )}
              </div>
            )}
          </SectionCard>
        ) : null}

        {tab === "dues" ? (
          <div className="stack">
            <SectionCard title={t("platform.dues")}>
              {duesQuery.isLoading ? (
                <Spinner label={t("common.loading")} />
              ) : (duesQuery.data ?? []).length === 0 ? (
                <EmptyState
                  icon={<Landmark size={24} />}
                  title={t("platform.empty")}
                />
              ) : (
                <div className="stack">
                  {(duesQuery.data ?? []).map((row) => (
                    <div className="row row--between" key={row.gym_id}>
                      <span>{row.gym_id}</span>
                      <span>
                        {row.stage} · {formatNumber(row.open_irr)} ·{" "}
                        {formatNumber(row.overdue_irr)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
            <SectionCard title={t("platform.reminders")}>
              <p className="muted">
                {(remindersQuery.data?.delivery_scope ?? "IN_APP_ONLY") ===
                "IN_APP_ONLY"
                  ? t("platform.inAppOnly")
                  : ""}
              </p>
              {(remindersQuery.data?.overdue ?? []).map((row) => (
                <div className="row row--between" key={row.id}>
                  <span>#{row.invoice_number}</span>
                  <span>{formatNumber(row.balance_irr)}</span>
                </div>
              ))}
            </SectionCard>
          </div>
        ) : null}
      </div>

      <Dialog
        open={planOpen}
        title={t("platform.newPlan")}
        onClose={() => setPlanOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setPlanOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void createPlan()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <TextField
            label={t("platform.code")}
            value={planForm.code}
            onChange={(event) =>
              setPlanForm({ ...planForm, code: event.target.value })
            }
          />
          <TextField
            label={t("platform.name")}
            value={planForm.name}
            onChange={(event) =>
              setPlanForm({ ...planForm, name: event.target.value })
            }
          />
          <TextField
            label={t("platform.price")}
            value={planForm.price}
            onChange={(event) =>
              setPlanForm({ ...planForm, price: event.target.value })
            }
          />
        </div>
      </Dialog>

      <Dialog
        open={agreementOpen}
        title={t("platform.newAgreement")}
        onClose={() => setAgreementOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setAgreementOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void createAgreement()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <SelectField
            label={t("platform.gym")}
            value={agreementForm.gym_id}
            onChange={(value) =>
              setAgreementForm({
                ...agreementForm,
                gym_id: value,
                group_id: "",
              })
            }
            options={gymOptions}
          />
          <SelectField
            label={t("platform.group")}
            value={agreementForm.group_id}
            onChange={(value) =>
              setAgreementForm({
                ...agreementForm,
                group_id: value,
                gym_id: "",
              })
            }
            options={[
              { value: "", label: "—" },
              ...(groupsQuery.data ?? []).map((group) => ({
                value: group.id,
                label: group.name,
              })),
            ]}
          />
          <SelectField
            label={t("platform.mode")}
            value={agreementForm.mode}
            onChange={(value) =>
              setAgreementForm({ ...agreementForm, mode: value })
            }
            options={MODES}
          />
          <TextField
            label={t("platform.subscriptionAmount")}
            value={agreementForm.amount}
            onChange={(event) =>
              setAgreementForm({ ...agreementForm, amount: event.target.value })
            }
          />
          <TextField
            label={t("platform.percent")}
            value={agreementForm.percent}
            onChange={(event) =>
              setAgreementForm({
                ...agreementForm,
                percent: event.target.value,
              })
            }
          />
          <DateField
            label={t("platform.effectiveFrom")}
            value={agreementForm.effective_from}
            onChange={(value) =>
              setAgreementForm({
                ...agreementForm,
                effective_from: value ?? today(),
              })
            }
            required
          />
        </div>
      </Dialog>

      <Dialog
        open={invoiceOpen}
        title={t("platform.newInvoice")}
        onClose={() => setInvoiceOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setInvoiceOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void issueInvoice()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <SelectField
            label={t("platform.gym")}
            value={invoiceForm.gym_id}
            onChange={(value) => setInvoiceForm({ gym_id: value })}
            options={gymOptions}
          />
        </div>
      </Dialog>

      <Dialog
        open={paymentTarget !== null}
        title={t("platform.pay")}
        onClose={() => setPaymentTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setPaymentTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void recordPayment()}>
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <TextField
            label={t("platform.amount")}
            value={paymentAmount}
            onChange={(event) => setPaymentAmount(event.target.value)}
          />
        </div>
      </Dialog>

      <Dialog
        open={versionPlan !== null}
        title={t("platform.newVersion")}
        onClose={() => setVersionPlan(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setVersionPlan(null)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void createVersion()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <DateField
            label={t("platform.effectiveFrom")}
            value={versionForm.effective_from}
            onChange={(value) =>
              setVersionForm({
                ...versionForm,
                effective_from: value ?? tomorrow(),
              })
            }
            required
          />
          <TextField
            label={t("platform.price")}
            value={versionForm.price}
            onChange={(event) =>
              setVersionForm({ ...versionForm, price: event.target.value })
            }
          />
        </div>
      </Dialog>

      <Dialog
        open={groupOpen}
        title={t("platform.newGroup")}
        onClose={() => setGroupOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setGroupOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={!groupForm.name.trim() || !groupForm.gym_id}
              onClick={() => void createGroup()}
            >
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <TextField
            label={t("platform.name")}
            value={groupForm.name}
            onChange={(event) =>
              setGroupForm({ ...groupForm, name: event.target.value })
            }
          />
          <SelectField
            label={t("platform.gym")}
            value={groupForm.gym_id}
            onChange={(value) => setGroupForm({ ...groupForm, gym_id: value })}
            options={gymOptions}
          />
        </div>
      </Dialog>

      <Dialog
        open={costOpen}
        title={t("platform.newCost")}
        onClose={() => setCostOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setCostOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void createCost()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <TextField
            label={t("platform.category")}
            value={costForm.category}
            onChange={(event) =>
              setCostForm({ ...costForm, category: event.target.value })
            }
          />
          <TextField
            label={t("platform.amount")}
            value={costForm.amount}
            onChange={(event) =>
              setCostForm({ ...costForm, amount: event.target.value })
            }
          />
          <DateField
            label={t("platform.effectiveFrom")}
            value={costForm.incurred_on}
            onChange={(value) =>
              setCostForm({ ...costForm, incurred_on: value ?? today() })
            }
            required
          />
          <SelectField
            label={t("platform.gym")}
            value={costForm.gym_id}
            onChange={(value) => setCostForm({ ...costForm, gym_id: value })}
            options={[{ value: "", label: "—" }, ...gymOptions]}
          />
        </div>
      </Dialog>

      <Dialog
        open={cancelTarget !== null}
        title={t("platform.cancelInvoice")}
        onClose={() => setCancelTarget(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setCancelTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              disabled={cancelReason.trim().length < 3}
              onClick={() => cancelTarget && void cancelInvoice(cancelTarget)}
            >
              {t("common.confirm")}
            </Button>
          </>
        }
      >
        <TextField
          label={t("platform.cancelReason")}
          value={cancelReason}
          onChange={(event) => setCancelReason(event.target.value)}
          multiline
        />
      </Dialog>
    </>
  )
}
