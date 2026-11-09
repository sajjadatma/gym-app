import { useQuery, useQueryClient } from "@tanstack/react-query"
import { FileSignature, Plus } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
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
  StatusBadge,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import {
  activatePlatformContract,
  archivePlatformContract,
  createPlatformContract,
  listPlatformContracts,
  type PlatformContract,
  updatePlatformContract,
} from "@/lib/finance-api"
import { bpFromPercent, percentFromBp, todayIso } from "@/lib/finance-ui"
import { useSnackbar } from "@/snackbar"

const CATEGORIES = [
  { key: "MEMBERSHIP" as const, label: "حق عضویت" },
  { key: "NUTRITION" as const, label: "برنامه تغذیه" },
  { key: "TRAINING" as const, label: "برنامه تمرینی" },
]

export function FinancePlatformContractsPage() {
  const { t, formatDate, normalizeDigits } = useI18n()
  const { gyms } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [open, setOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: "",
    scope: "DEFAULT" as "DEFAULT" | "GYM",
    gymId: "",
    effectiveFrom: todayIso(),
    effectiveTo: "",
    rates: { MEMBERSHIP: "10", NUTRITION: "12", TRAINING: "15" },
  })
  const contracts = useQuery({
    queryKey: ["finance-platform-contracts"],
    queryFn: () => listPlatformContracts(),
  })

  function openCreate() {
    setEditingId(null)
    setError(null)
    setForm({
      name: "",
      scope: "DEFAULT",
      gymId: "",
      effectiveFrom: todayIso(),
      effectiveTo: "",
      rates: { MEMBERSHIP: "10", NUTRITION: "12", TRAINING: "15" },
    })
    setOpen(true)
  }

  function openEdit(row: PlatformContract) {
    const rateValue = (
      category: PlatformContract["rates"][number]["category"],
    ) =>
      percentFromBp(
        row.rates.find((rate) => rate.category === category)?.percent_bp ?? 0,
      )
    setEditingId(row.id)
    setError(null)
    setForm({
      name: row.name,
      scope: row.scope,
      gymId: row.gym_id ?? "",
      effectiveFrom: todayIso(),
      effectiveTo:
        row.effective_to && row.effective_to >= todayIso()
          ? row.effective_to
          : "",
      rates: {
        MEMBERSHIP: rateValue("MEMBERSHIP"),
        NUTRITION: rateValue("NUTRITION"),
        TRAINING: rateValue("TRAINING"),
      },
    })
    setOpen(true)
  }

  async function submit() {
    const rates = CATEGORIES.map((category) => ({
      category: category.key,
      percent_bp: bpFromPercent(
        Number(normalizeDigits(form.rates[category.key])) || 0,
      ),
    }))
    setSaving(true)
    setError(null)
    try {
      if (editingId) {
        await updatePlatformContract(editingId, {
          name: form.name.trim(),
          effective_from: form.effectiveFrom,
          effective_to: form.effectiveTo || null,
          rates,
        })
      } else {
        await createPlatformContract({
          name: form.name.trim(),
          scope: form.scope,
          gym_id: form.scope === "GYM" ? form.gymId : null,
          effective_from: form.effectiveFrom,
          effective_to: form.effectiveTo || null,
          rates,
        })
      }
      await queryClient.invalidateQueries({
        queryKey: ["finance-platform-contracts"],
      })
      await queryClient.invalidateQueries({ queryKey: ["finance-policy"] })
      await queryClient.invalidateQueries({
        queryKey: ["finance-coach-contracts"],
      })
      show(t("common.success"), "success")
      setOpen(false)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function activate(row: PlatformContract) {
    setError(null)
    try {
      await activatePlatformContract(row.id)
      await queryClient.invalidateQueries({
        queryKey: ["finance-platform-contracts"],
      })
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    }
  }

  async function archive(row: PlatformContract) {
    setError(null)
    try {
      await archivePlatformContract(row.id)
      await queryClient.invalidateQueries({
        queryKey: ["finance-platform-contracts"],
      })
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    }
  }

  if (contracts.isLoading) return <Spinner label={t("common.loading")} />
  if (contracts.isError) {
    return (
      <ErrorState
        message={translateApiError(contracts.error, t)}
        onRetry={() => void contracts.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={t("finance.platformContracts.title")}
        subtitle={t("finance.platformContracts.subtitle")}
        actions={
          <Button icon={<Plus size={17} />} onClick={openCreate}>
            {t("finance.platformContracts.new")}
          </Button>
        }
      />
      <div className="m3-finance-note">
        <FileSignature size={18} aria-hidden />
        <span>{t("finance.platformContracts.note")}</span>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <SectionCard>
        <div className="m3-filter-bar">
          <SelectField
            label={t("finance.table.status")}
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: "", label: t("common.all") },
              { value: "DRAFT", label: t("status.draft") },
              { value: "ACTIVE", label: t("status.active") },
              { value: "ARCHIVED", label: t("status.archived") },
            ]}
          />
        </div>
      </SectionCard>
      {contracts.data?.length === 0 ? (
        <EmptyState
          icon={<FileSignature size={24} />}
          title={t("finance.platformContracts.empty")}
          description={t("finance.platformContracts.emptyHint")}
        />
      ) : (
        <SectionCard title={t("finance.platformContracts.listTitle")}>
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("finance.table.name")}</th>
                  <th>{t("finance.table.scope")}</th>
                  <th>{t("finance.table.gym")}</th>
                  <th>{t("finance.table.rates")}</th>
                  <th>{t("finance.table.effective")}</th>
                  <th>{t("finance.table.version")}</th>
                  <th>{t("finance.table.status")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {contracts.data
                  ?.filter(
                    (row) => !statusFilter || row.status === statusFilter,
                  )
                  .map((row) => (
                    <tr key={row.id}>
                      <td>{row.name}</td>
                      <td>
                        {row.scope === "DEFAULT"
                          ? t("finance.platformContracts.defaultScope")
                          : t("finance.platformContracts.gymScope")}
                      </td>
                      <td>
                        {row.gym_id
                          ? (gyms.find((gym) => gym.id === row.gym_id)?.name ??
                            row.gym_id)
                          : "—"}
                      </td>
                      <td>
                        {row.rates.map((rate) => (
                          <div key={rate.category}>
                            {
                              CATEGORIES.find(
                                (item) => item.key === rate.category,
                              )?.label
                            }
                            : {percentFromBp(rate.percent_bp)}٪
                          </div>
                        ))}
                      </td>
                      <td>
                        {formatDate(row.effective_from)}
                        {row.effective_to
                          ? ` — ${formatDate(row.effective_to)}`
                          : ""}
                      </td>
                      <td>{row.version}</td>
                      <td>
                        <StatusBadge status={row.status.toLowerCase()} />
                      </td>
                      <td>
                        <div className="m3-inline-actions">
                          <Button
                            size="sm"
                            variant="text"
                            onClick={() => openEdit(row)}
                          >
                            {t("common.edit")}
                          </Button>
                          {row.status === "DRAFT" ? (
                            <Button
                              size="sm"
                              variant="tonal"
                              onClick={() => void activate(row)}
                            >
                              {t("finance.platformContracts.activate")}
                            </Button>
                          ) : null}
                          {row.status !== "ARCHIVED" ? (
                            <Button
                              size="sm"
                              variant="text"
                              onClick={() => void archive(row)}
                            >
                              {t("finance.contracts.archive")}
                            </Button>
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
        title={
          editingId
            ? t("finance.platformContracts.editTitle")
            : t("finance.platformContracts.dialogTitle")
        }
        description={t("finance.platformContracts.dialogDescription")}
        onClose={() => setOpen(false)}
        size="lg"
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
              {t("finance.common.saveApply")}
            </Button>
          </>
        }
      >
        <div className="m3-form-grid">
          <TextField
            label={t("finance.table.name")}
            value={form.name}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, name: event.target.value }))
            }
            required
          />
          <SelectField
            label={t("finance.table.scope")}
            value={form.scope}
            onChange={(value) =>
              setForm((prev) => ({
                ...prev,
                scope: value as "DEFAULT" | "GYM",
              }))
            }
            options={[
              {
                value: "DEFAULT",
                label: t("finance.platformContracts.defaultScope"),
              },
              { value: "GYM", label: t("finance.platformContracts.gymScope") },
            ]}
            disabled={Boolean(editingId)}
          />
          {form.scope === "GYM" ? (
            <SelectField
              label={t("finance.table.gym")}
              value={form.gymId}
              onChange={(value) =>
                setForm((prev) => ({ ...prev, gymId: value }))
              }
              options={gyms.map((gym) => ({ value: gym.id, label: gym.name }))}
              required
              disabled={Boolean(editingId)}
            />
          ) : null}
          <DateField
            label={t("finance.contracts.effectiveFrom")}
            value={form.effectiveFrom}
            onChange={(value) =>
              setForm((prev) => ({
                ...prev,
                effectiveFrom: value ?? todayIso(),
              }))
            }
          />
          <DateField
            label={t("finance.contracts.effectiveTo")}
            value={form.effectiveTo}
            onChange={(value) =>
              setForm((prev) => ({ ...prev, effectiveTo: value ?? "" }))
            }
            helper={t("common.optional")}
          />
          {CATEGORIES.map((category) => (
            <TextField
              key={category.key}
              label={`${category.label} (${t("finance.table.platformPercent")})`}
              value={form.rates[category.key]}
              onChange={(event) =>
                setForm((prev) => ({
                  ...prev,
                  rates: { ...prev.rates, [category.key]: event.target.value },
                }))
              }
              inputMode="decimal"
              suffix="٪"
            />
          ))}
        </div>
        <p className="m3-field__message">
          {t("finance.platformContracts.rateHint")}
        </p>
        {error ? <ErrorState message={error} /> : null}
      </Dialog>
    </div>
  )
}
