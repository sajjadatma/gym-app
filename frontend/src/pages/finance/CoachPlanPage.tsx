import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ClipboardList, Plus, Wallet } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
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
  type CoachPlan,
  createCoachPlan,
  listCoachPlans,
  listGymCoaches,
  listGymProgramRequests,
  updateCoachPlan,
} from "@/lib/finance-api"
import { formatToman, irrToToman, tomanToIrr } from "@/lib/finance-ui"
import { useSnackbar } from "@/snackbar"

const EMPTY_FORM = {
  coachId: "",
  title: "",
  description: "",
  priceToman: "",
  active: true,
}

export function CoachPlanPage({ gymId }: { gymId: string }) {
  const { t, formatNumber, formatDate, normalizeDigits } = useI18n()
  const { me, activeRole } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const isAdmin = activeRole !== "COACH"
  const [open, setOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  const plans = useQuery({
    queryKey: ["finance-coach-plans", gymId, isAdmin ? "all" : me?.id],
    queryFn: () =>
      listCoachPlans(gymId, isAdmin ? undefined : (me?.id ?? undefined)),
  })
  const coaches = useQuery({
    queryKey: ["finance-coaches", gymId],
    queryFn: () => listGymCoaches(gymId),
    enabled: isAdmin,
  })
  const requests = useQuery({
    queryKey: ["finance-program-requests", gymId],
    queryFn: () => listGymProgramRequests(gymId),
  })

  function openCreate() {
    setEditingId(null)
    setError(null)
    setForm({
      ...EMPTY_FORM,
      coachId: isAdmin ? "" : (me?.id ?? ""),
    })
    setOpen(true)
  }

  function openEdit(plan: CoachPlan) {
    setEditingId(plan.id)
    setError(null)
    setForm({
      coachId: plan.coach_user_id,
      title: plan.title,
      description: plan.description ?? "",
      priceToman: String(irrToToman(plan.base_price_irr)),
      active: plan.is_active,
    })
    setOpen(true)
  }

  async function submit() {
    const price = Number(normalizeDigits(form.priceToman)) || 0
    if (!form.title.trim() || price <= 0) {
      setError(t("finance.plans.errorRequired"))
      return
    }
    if (isAdmin && !editingId && !form.coachId) {
      setError(t("finance.plans.errorCoach"))
      return
    }
    setSaving(true)
    setError(null)
    try {
      if (editingId) {
        await updateCoachPlan(gymId, editingId, {
          title: form.title.trim(),
          description: form.description.trim() || null,
          base_price_irr: tomanToIrr(price),
          is_active: form.active,
        })
      } else {
        await createCoachPlan(gymId, {
          coach_user_id: isAdmin ? form.coachId : null,
          title: form.title.trim(),
          description: form.description.trim() || null,
          base_price_irr: tomanToIrr(price),
          is_active: form.active,
        })
      }
      await queryClient.invalidateQueries({
        queryKey: ["finance-coach-plans", gymId],
      })
      show(t("common.success"), "success")
      setOpen(false)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  if (plans.isLoading || requests.isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (plans.isError) {
    return (
      <ErrorState
        message={translateApiError(plans.error, t)}
        onRetry={() => void plans.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={t("finance.plans.title")}
        subtitle={t("finance.plans.subtitle")}
        actions={
          <Button icon={<Plus size={17} />} onClick={openCreate}>
            {t("finance.plans.new")}
          </Button>
        }
      />
      <div className="m3-finance-note">
        <Wallet size={18} aria-hidden />
        <span>{t("finance.plans.note")}</span>
      </div>
      {error && !open ? <ErrorState message={error} /> : null}

      {plans.data?.length === 0 ? (
        <EmptyState
          icon={<Wallet size={24} />}
          title={t("finance.plans.empty")}
          description={t("finance.plans.emptyHint")}
          action={
            <Button icon={<Plus size={17} />} onClick={openCreate}>
              {t("finance.plans.new")}
            </Button>
          }
        />
      ) : (
        <SectionCard title={t("finance.plans.listTitle")}>
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("finance.plans.planTitle")}</th>
                  {isAdmin ? <th>{t("finance.table.coach")}</th> : null}
                  <th>{t("finance.plans.price")}</th>
                  <th>{t("finance.table.status")}</th>
                  <th>{t("finance.plans.updatedAt")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {plans.data?.map((plan) => (
                  <tr key={plan.id}>
                    <td>
                      <strong>{plan.title}</strong>
                      {plan.description ? (
                        <small className="m3-table__hint">
                          {plan.description}
                        </small>
                      ) : null}
                    </td>
                    {isAdmin ? <td>{plan.coach_name ?? "—"}</td> : null}
                    <td>{formatToman(plan.base_price_irr, formatNumber)}</td>
                    <td>
                      <span className="m3-status">
                        {plan.is_active
                          ? t("finance.plans.active")
                          : t("finance.plans.inactive")}
                      </span>
                    </td>
                    <td>{formatDate(plan.updated_at)}</td>
                    <td>
                      <Button
                        size="sm"
                        variant="text"
                        onClick={() => openEdit(plan)}
                      >
                        {t("common.edit")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <SectionCard title={t("finance.requests.title")}>
        {requests.data?.length ? (
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("finance.requests.athlete")}</th>
                  <th>{t("finance.plans.planTitle")}</th>
                  <th>{t("finance.requests.amount")}</th>
                  <th>{t("finance.requests.note")}</th>
                  <th>{t("finance.table.status")}</th>
                  <th>{t("finance.requests.createdAt")}</th>
                </tr>
              </thead>
              <tbody>
                {requests.data.map((request) => (
                  <tr key={request.id}>
                    <td>{request.athlete_name ?? "—"}</td>
                    <td>{request.plan_title}</td>
                    <td>
                      {formatToman(request.total_amount_irr, formatNumber)}
                    </td>
                    <td>{request.note ?? "—"}</td>
                    <td>
                      <span className="m3-status">
                        {request.status === "REQUESTED"
                          ? t("finance.requests.statusRequested")
                          : t("finance.requests.statusFulfilled")}
                      </span>
                    </td>
                    <td>{formatDate(request.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={<ClipboardList size={24} />}
            title={t("finance.requests.empty")}
            description={t("finance.requests.emptyHint")}
          />
        )}
      </SectionCard>

      <Dialog
        open={open}
        title={
          editingId
            ? t("finance.plans.editTitle")
            : t("finance.plans.dialogTitle")
        }
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void submit()} loading={saving}>
              {t("finance.plans.save")}
            </Button>
          </>
        }
      >
        <div className="m3-form-grid">
          {isAdmin ? (
            <SelectField
              label={t("finance.table.coach")}
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
          ) : null}
          <TextField
            label={t("finance.plans.planTitle")}
            value={form.title}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, title: event.target.value }))
            }
            required
          />
          <TextField
            label={t("finance.plans.priceToman")}
            value={form.priceToman}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, priceToman: event.target.value }))
            }
            inputMode="numeric"
            suffix={t("finance.plans.toman")}
            required
          />
          <TextField
            label={t("finance.plans.description")}
            value={form.description}
            onChange={(event) =>
              setForm((prev) => ({
                ...prev,
                description: event.target.value,
              }))
            }
            multiline
          />
          <SelectField
            label={t("finance.table.status")}
            value={form.active ? "active" : "inactive"}
            onChange={(value) =>
              setForm((prev) => ({ ...prev, active: value === "active" }))
            }
            options={[
              { value: "active", label: t("finance.plans.active") },
              { value: "inactive", label: t("finance.plans.inactive") },
            ]}
          />
        </div>
        <p className="m3-field__message">{t("finance.plans.activeHint")}</p>
        {error ? <ErrorState message={error} /> : null}
      </Dialog>
    </div>
  )
}
