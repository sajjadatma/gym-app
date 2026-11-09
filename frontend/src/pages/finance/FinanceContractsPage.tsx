import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { FileSignature, Plus } from "lucide-react"
import { useState } from "react"
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
} from "@/lib/finance-api"
import {
  bpFromPercent,
  categoryLabel,
  percentFromBp,
  sourceLabel,
  todayIso,
} from "@/lib/finance-ui"
import { useSnackbar } from "@/snackbar"

const CATEGORY_OPTIONS: { value: FinanceCategory; label: string }[] = [
  { value: "MEMBERSHIP", label: categoryLabel("MEMBERSHIP") },
  { value: "NUTRITION", label: categoryLabel("NUTRITION") },
  { value: "TRAINING", label: categoryLabel("TRAINING") },
]

export function FinanceContractsPage({ gymId }: { gymId: string }) {
  const { t, formatNumber, formatDate, normalizeDigits } = useI18n()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    coachId: "",
    category: "MEMBERSHIP" as FinanceCategory,
    effectiveFrom: todayIso(),
    effectiveTo: "",
    gymPercent: "40",
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
  const gymPercent = Number(normalizeDigits(form.gymPercent)) || 0
  const coachPercent = Number(normalizeDigits(form.coachPercent)) || 0
  const remaining =
    platformPercent === null
      ? null
      : 100 - platformPercent - gymPercent - coachPercent
  const formError = (() => {
    if (!form.coachId) return t("finance.contracts.errorCoach")
    if (!form.effectiveFrom) return t("finance.contracts.errorDate")
    if (form.effectiveTo && form.effectiveTo < form.effectiveFrom) {
      return t("finance.contracts.errorDates")
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

  async function submit() {
    if (formError || !policy.data) return
    setSaving(true)
    setError(null)
    try {
      await createCoachContract(gymId, {
        coach_user_id: form.coachId,
        category: form.category,
        effective_from: form.effectiveFrom,
        effective_to: form.effectiveTo || null,
        platform_bp: policy.data.platform_bp,
        gym_bp: bpFromPercent(gymPercent),
        coach_bp: bpFromPercent(coachPercent),
      })
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
          <Button icon={<Plus size={17} />} onClick={() => setOpen(true)}>
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
            <Button icon={<Plus size={17} />} onClick={() => setOpen(true)}>
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
        title={t("finance.contracts.dialogTitle")}
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
              {t("finance.contracts.saveDraft")}
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
            required
          />
          <TextField
            label={t("finance.table.coachPercent")}
            value={form.coachPercent}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, coachPercent: event.target.value }))
            }
            inputMode="decimal"
            suffix="٪"
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
