import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FileSignature, Plus } from "lucide-react"
import { useEffect, useState } from "react"
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
  StatusBadge,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import {
  activateCoachContract,
  archiveCoachContract,
  type CoachContract,
  createCoachContract,
  type FinanceCategory,
  getPlatformPolicy,
  listCoachContracts,
  listGymCoaches,
  updateCoachContract,
} from "@/lib/finance-api"
import {
  categoryLabel,
  parsePercentToBp,
  percentFromBp,
  sourceLabel,
  todayIso,
} from "@/lib/finance-ui"
import { parseErrorMessage } from "@/lib/finance-validation"
import { useSnackbar } from "@/snackbar"

const CATEGORY_OPTIONS: { value: FinanceCategory; label: string }[] = [
  { value: "NUTRITION", label: categoryLabel("NUTRITION") },
  { value: "TRAINING", label: categoryLabel("TRAINING") },
]

export function FinanceContractsPage({ gymId }: { gymId: string }) {
  const { t, formatNumber, formatDate } = useI18n()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [open, setOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    coachId: "",
    category: "TRAINING" as FinanceCategory,
    effectiveFrom: todayIso(),
    effectiveTo: "",
    gymPercent: "35",
    coachPercent: "50",
  })
  const contracts = useQuery({
    queryKey: ["finance-coach-contracts", gymId],
    queryFn: () => listCoachContracts(gymId),
  })
  const coaches = useQuery({
    queryKey: ["finance-coaches", gymId],
    queryFn: () => listGymCoaches(gymId),
  })
  const policy = useQuery({
    queryKey: ["finance-policy", gymId, form.category, form.effectiveFrom],
    queryFn: () => getPlatformPolicy(gymId, form.category, form.effectiveFrom),
    enabled: open,
  })
  const platformPercent = policy.data ? policy.data.platform_bp / 100 : null
  const gymParse = parsePercentToBp(form.gymPercent)
  const coachParse = parsePercentToBp(form.coachPercent)
  const gymPercent = gymParse.ok ? gymParse.value / 100 : 0
  const coachPercent = coachParse.ok ? coachParse.value / 100 : 0
  const gymFieldError = form.gymPercent
    ? parseErrorMessage(gymParse, "percent", t)
    : undefined
  const coachFieldError = form.coachPercent
    ? parseErrorMessage(coachParse, "percent", t)
    : undefined
  const remaining =
    platformPercent === null
      ? null
      : 100 - platformPercent - gymPercent - coachPercent
  useEffect(() => {
    if (!open || !editingId || !policy.data) return
    const nextGym =
      Math.round((100 - policy.data.platform_bp / 100 - coachPercent) * 100) /
      100
    if (Math.abs(nextGym - gymPercent) > 0.0001) {
      setForm((prev) => ({ ...prev, gymPercent: String(nextGym) }))
    }
  }, [open, editingId, policy.data, coachPercent, gymPercent])
  const formError = (() => {
    if (!form.coachId) return t("finance.contracts.errorCoach")
    if (!form.effectiveFrom) return t("finance.contracts.errorDate")
    if (form.effectiveTo && form.effectiveTo < form.effectiveFrom) {
      return t("finance.contracts.errorDates")
    }
    if (!gymParse.ok || !coachParse.ok) {
      return (
        gymFieldError ?? coachFieldError ?? t("finance.contracts.errorBounds")
      )
    }
    if (
      gymPercent < 0 ||
      gymPercent > 100 ||
      coachPercent < 0 ||
      coachPercent > 100
    ) {
      return t("finance.contracts.errorBounds")
    }
    if (remaining === null) return t("finance.contracts.errorPolicy")
    if (Math.abs(remaining) > 0.0001) return t("finance.contracts.errorTotal")
    return null
  })()

  function openCreate() {
    setEditingId(null)
    setError(null)
    setForm({
      coachId: "",
      category: "TRAINING",
      effectiveFrom: todayIso(),
      effectiveTo: "",
      gymPercent: "35",
      coachPercent: "50",
    })
    setOpen(true)
  }

  function openEdit(row: CoachContract) {
    const today = todayIso()
    setEditingId(row.id)
    setError(null)
    setForm({
      coachId: row.coach_user_id,
      category: row.category,
      effectiveFrom: today,
      effectiveTo:
        row.effective_to && row.effective_to >= today ? row.effective_to : "",
      gymPercent: percentFromBp(row.gym_bp),
      coachPercent: percentFromBp(row.coach_bp),
    })
    setOpen(true)
  }

  async function submit() {
    if (formError || !policy.data || !gymParse.ok || !coachParse.ok) return
    setSaving(true)
    setError(null)
    try {
      if (editingId) {
        await updateCoachContract(gymId, editingId, {
          effective_from: form.effectiveFrom,
          effective_to: form.effectiveTo || null,
          platform_bp: policy.data.platform_bp,
          gym_bp: gymParse.value,
          coach_bp: coachParse.value,
        })
      } else {
        await createCoachContract(gymId, {
          coach_user_id: form.coachId,
          category: form.category,
          effective_from: form.effectiveFrom,
          effective_to: form.effectiveTo || null,
          platform_bp: policy.data.platform_bp,
          gym_bp: gymParse.value,
          coach_bp: coachParse.value,
        })
      }
      await queryClient.invalidateQueries({
        queryKey: ["finance-coach-contracts", gymId],
      })
      show(t("common.success"), "success")
      setOpen(false)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function activate(row: CoachContract) {
    setError(null)
    try {
      await activateCoachContract(gymId, row.id)
      await queryClient.invalidateQueries({
        queryKey: ["finance-coach-contracts", gymId],
      })
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    }
  }

  async function archive(row: CoachContract) {
    setError(null)
    try {
      await archiveCoachContract(gymId, row.id)
      await queryClient.invalidateQueries({
        queryKey: ["finance-coach-contracts", gymId],
      })
      show(t("common.success"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    }
  }

  const mutation = useMutation({ mutationFn: submit })

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={t("finance.contracts.title")}
        subtitle={t("finance.contracts.subtitle")}
        actions={
          <Button icon={<Plus size={17} />} onClick={openCreate}>
            {t("finance.contracts.new")}
          </Button>
        }
      />
      <div className="m3-finance-note">
        <FileSignature size={18} aria-hidden />
        <span>{t("finance.contracts.note")}</span>
      </div>
      {error ? <ErrorState message={error} /> : null}
      {contracts.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : contracts.isError ? (
        <ErrorState
          message={translateApiError(contracts.error, t)}
          onRetry={() => void contracts.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : contracts.data?.length === 0 ? (
        <EmptyState
          icon={<FileSignature size={24} />}
          title={t("finance.contracts.empty")}
          description={t("finance.contracts.emptyHint")}
          action={
            <Button icon={<Plus size={17} />} onClick={openCreate}>
              {t("finance.contracts.new")}
            </Button>
          }
        />
      ) : (
        <SectionCard title={t("finance.contracts.listTitle")}>
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("finance.table.coach")}</th>
                  <th>{t("finance.table.category")}</th>
                  <th>{t("finance.table.platformPercent")}</th>
                  <th>{t("finance.table.gymPercent")}</th>
                  <th>{t("finance.table.coachPercent")}</th>
                  <th>{t("finance.table.effective")}</th>
                  <th>{t("finance.table.status")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {contracts.data?.map((row) => (
                  <tr key={row.id}>
                    <td>{row.coach_name ?? "—"}</td>
                    <td>{categoryLabel(row.category)}</td>
                    <td>
                      {percentFromBp(row.platform_bp)}٪
                      <small className="m3-table__hint">
                        {sourceLabel(row.platform_source)}
                      </small>
                    </td>
                    <td>{percentFromBp(row.gym_bp)}٪</td>
                    <td>{percentFromBp(row.coach_bp)}٪</td>
                    <td>
                      {formatDate(row.effective_from)}
                      {row.effective_to
                        ? ` — ${formatDate(row.effective_to)}`
                        : ""}
                    </td>
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
                            {t("finance.contracts.activate")}
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
            ? t("finance.contracts.editTitle")
            : t("finance.contracts.dialogTitle")
        }
        description={t("finance.contracts.dialogDescription")}
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
            <Button
              onClick={() => mutation.mutate()}
              loading={saving}
              disabled={Boolean(formError) || policy.isLoading}
            >
              {t("finance.contracts.saveApply")}
            </Button>
          </>
        }
      >
        <div className="m3-form-grid">
          <SelectField
            label={t("finance.contracts.coach")}
            value={form.coachId}
            onChange={(value) =>
              setForm((prev) => ({ ...prev, coachId: value }))
            }
            options={(coaches.data ?? []).map((coach) => ({
              value: coach.user_id,
              label: `${coach.name} (${coach.email})`,
            }))}
            required
            disabled={Boolean(editingId)}
          />
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
            required
            disabled={Boolean(editingId)}
          />
          <DateField
            label={t("finance.contracts.effectiveFrom")}
            value={form.effectiveFrom}
            onChange={(value) =>
              setForm((prev) => ({ ...prev, effectiveFrom: value ?? "" }))
            }
            required
          />
          <DateField
            label={t("finance.contracts.effectiveTo")}
            value={form.effectiveTo}
            onChange={(value) =>
              setForm((prev) => ({ ...prev, effectiveTo: value ?? "" }))
            }
            helper={t("common.optional")}
          />
          <TextField
            label={t("finance.table.platformPercent")}
            value={
              policy.data === undefined
                ? "…"
                : `${percentFromBp(policy.data.platform_bp)}٪`
            }
            disabled
            readOnly
            helper={
              policy.data
                ? `${t("finance.contracts.platformReadOnly")} — ${sourceLabel(policy.data.source)}`
                : t("finance.contracts.platformLoading")
            }
          />
          <TextField
            label={t("finance.table.gymPercent")}
            value={form.gymPercent}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, gymPercent: event.target.value }))
            }
            inputMode="decimal"
            suffix="٪"
            error={gymFieldError}
            required
            readOnly={Boolean(editingId)}
            helper={
              editingId ? t("finance.contracts.gymAutoAdjusted") : undefined
            }
          />
          <TextField
            label={t("finance.table.coachPercent")}
            value={form.coachPercent}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, coachPercent: event.target.value }))
            }
            inputMode="decimal"
            suffix="٪"
            error={coachFieldError}
            required
          />
          <div
            className={`m3-remaining ${remaining === 0 ? "is-valid" : "is-invalid"}`}
          >
            <span>{t("finance.contracts.remaining")}</span>
            <strong>
              {remaining === null ? "…" : `${formatNumber(remaining)}٪`}
            </strong>
          </div>
        </div>
        <p className="m3-field__message">{t("finance.contracts.editHint")}</p>
        {formError ? <ErrorState message={formError} /> : null}
        {error ? <ErrorState message={error} /> : null}
      </Dialog>
    </div>
  )
}
