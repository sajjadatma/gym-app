import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Copy, Mail, Plus, Search, UserRound, Users } from "lucide-react"
import { useDeferredValue, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type AthleteCreated, AthletesService, GymsService } from "@/client"
import {
  Avatar,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  SelectField,
  Spinner,
  StatusBadge,
  Switch,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function AthletesPage() {
  const { t, formatNumber } = useI18n()
  const { activeGym, activeGymId, activeRole, isAdmin, me } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [created, setCreated] = useState<AthleteCreated | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    phone: "",
    coach_user_id: "",
    activation_method: "invite" as "invite" | "password",
    initial_password: "",
    height_cm: "",
    weight_kg: "",
    training_goal: "",
  })

  const canCreate = activeRole === "GYM_ADMIN" || activeRole === "COACH"

  const athletesQuery = useQuery({
    queryKey: [
      "athletes",
      activeGymId,
      deferredSearch,
      includeArchived,
      activeRole,
    ],
    queryFn: async () =>
      (
        await AthletesService.listAthletes({
          query: {
            q: deferredSearch,
            include_archived: includeArchived && isAdmin,
          },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })

  const coachesQuery = useQuery({
    queryKey: ["coaches", activeGymId],
    queryFn: async () =>
      (
        await GymsService.listCoaches({
          path: { gym_id: activeGymId! },
        })
      ).data.data,
    enabled: Boolean(activeGymId && isAdmin),
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("athletes.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  const athletes = (athletesQuery.data?.data ?? []).filter((athlete) => {
    if (activeRole === "COACH" && !isAdmin) {
      return athlete.coach_user_id === me?.id
    }
    return true
  })

  const coachOptions = (coachesQuery.data ?? []).map((coach) => ({
    value: coach.user_id,
    label: coach.full_name ?? coach.email,
  }))

  async function addAthlete() {
    setError(null)
    if (!/^\S+@\S+\.\S+$/.test(form.email)) {
      setError(t("validation.email"))
      return
    }
    if (isAdmin && !form.coach_user_id) {
      setError(t("athletes.coachRequired"))
      return
    }
    if (
      form.activation_method === "password" &&
      form.initial_password &&
      form.initial_password.length < 8
    ) {
      setError(t("validation.initialPassword"))
      return
    }
    setSaving(true)
    try {
      const response = await AthletesService.createAthlete({
        body: {
          email: form.email,
          full_name: form.full_name || null,
          phone: form.phone || null,
          coach_user_id: isAdmin ? form.coach_user_id : me?.id,
          activation_method: form.activation_method,
          initial_password:
            form.activation_method === "password"
              ? form.initial_password || null
              : null,
          height_cm: form.height_cm ? Number(form.height_cm) : null,
          weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
          training_goal: form.training_goal || null,
        },
      })
      await queryClient.invalidateQueries({
        queryKey: ["athletes", activeGymId],
      })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      setAddOpen(false)
      setCreated(response.data)
      setForm({
        email: "",
        full_name: "",
        phone: "",
        coach_user_id: "",
        activation_method: "invite",
        initial_password: "",
        height_cm: "",
        weight_kg: "",
        training_goal: "",
      })
      show(t("athletes.created"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t("athletes.title")}
        subtitle={`${activeGym.name} · ${t("athletes.subtitle")}`}
        actions={
          canCreate ? (
            <Button icon={<Plus size={17} />} onClick={() => setAddOpen(true)}>
              {t("athletes.add")}
            </Button>
          ) : undefined
        }
      />

      <div className="m3-filter-bar">
        <div className="m3-search">
          <Search size={18} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("athletes.search")}
            aria-label={t("athletes.search")}
          />
        </div>
        {isAdmin ? (
          <Switch
            checked={includeArchived}
            onChange={setIncludeArchived}
            label={t("status.archived")}
          />
        ) : null}
        <span className="muted" style={{ fontSize: 12 }}>
          {t("common.people")}: {formatNumber(athletes.length)}
        </span>
      </div>

      {athletesQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : athletesQuery.isError ? (
        <ErrorState
          message={translateApiError(athletesQuery.error, t)}
          onRetry={() => athletesQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : athletes.length === 0 ? (
        <EmptyState
          icon={<Users size={26} />}
          title={t("athletes.empty")}
          description={t("athletes.emptyHint")}
          action={
            canCreate ? (
              <Button
                icon={<Plus size={17} />}
                onClick={() => setAddOpen(true)}
              >
                {t("athletes.add")}
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="m3-card-grid">
          {athletes.map((athlete) => (
            <button
              key={athlete.user_id}
              type="button"
              className="m3-entity-card"
              style={{ textAlign: "start", fontFamily: "inherit" }}
              onClick={() =>
                navigate({
                  to: "/athletes/$athleteId",
                  params: { athleteId: athlete.user_id },
                })
              }
            >
              <div className="m3-entity-card__head">
                <div
                  className="row"
                  style={{ gap: 10, flexWrap: "nowrap", minWidth: 0 }}
                >
                  <Avatar name={athlete.full_name ?? athlete.email} />
                  <div style={{ minWidth: 0 }}>
                    <div className="m3-entity-card__title truncate">
                      {athlete.full_name ?? athlete.email}
                    </div>
                    <div className="m3-entity-card__meta">
                      <span className="truncate" dir="ltr">
                        {athlete.email}
                      </span>
                    </div>
                  </div>
                </div>
                {athlete.is_archived ? (
                  <StatusBadge status="archived" />
                ) : (
                  <StatusBadge
                    status={athlete.is_active ? "active" : "inactive"}
                  />
                )}
              </div>
              <div className="m3-entity-card__meta">
                <span>
                  <UserRound size={13} style={{ verticalAlign: "middle" }} />{" "}
                  {athlete.coach_name ?? t("athletes.noCoach")}
                </span>
                {athlete.phone ? <span dir="ltr">{athlete.phone}</span> : null}
              </div>
              <div className="m3-entity-card__footer">
                {athlete.active_program_title ? (
                  <span className="m3-status m3-status--active">
                    {athlete.active_program_title}
                  </span>
                ) : (
                  <span className="m3-status m3-status--archived">
                    {t("athletes.noActiveProgram")}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      <Dialog
        open={addOpen}
        title={t("athletes.addTitle")}
        onClose={() => setAddOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setAddOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={addAthlete} loading={saving}>
              {t("common.add")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <div className="grid-2">
            <TextField
              label={t("auth.email")}
              type="email"
              dir="ltr"
              value={form.email}
              onChange={(event) =>
                setForm({ ...form, email: event.target.value })
              }
              required
            />
            <TextField
              label={t("athletes.fullName")}
              value={form.full_name}
              onChange={(event) =>
                setForm({ ...form, full_name: event.target.value })
              }
              required
            />
          </div>
          <div className="grid-2">
            <TextField
              label={t("athletes.phone")}
              dir="ltr"
              value={form.phone}
              onChange={(event) =>
                setForm({ ...form, phone: event.target.value })
              }
            />
            {isAdmin ? (
              <SelectField
                label={t("athletes.coach")}
                value={form.coach_user_id}
                onChange={(value) => setForm({ ...form, coach_user_id: value })}
                options={coachOptions}
                placeholder={t("athletes.chooseCoach")}
                required
              />
            ) : null}
          </div>
          <div className="grid-2">
            <TextField
              label={t("athletes.height")}
              suffix={t("common.units.cm")}
              inputMode="decimal"
              value={form.height_cm}
              onChange={(event) =>
                setForm({ ...form, height_cm: event.target.value })
              }
            />
            <TextField
              label={t("athletes.weight")}
              suffix={t("common.units.kg")}
              inputMode="decimal"
              value={form.weight_kg}
              onChange={(event) =>
                setForm({ ...form, weight_kg: event.target.value })
              }
            />
          </div>
          <TextField
            label={t("athletes.goal")}
            value={form.training_goal}
            onChange={(event) =>
              setForm({ ...form, training_goal: event.target.value })
            }
          />
          <SelectField
            label={t("gyms.activationMethod")}
            value={form.activation_method}
            onChange={(value) =>
              setForm({
                ...form,
                activation_method: value as "invite" | "password",
              })
            }
            options={[
              { value: "invite", label: t("gyms.methodInvite") },
              { value: "password", label: t("gyms.methodPassword") },
            ]}
          />
          {form.activation_method === "password" ? (
            <TextField
              label={t("gyms.initialPassword")}
              type="text"
              dir="ltr"
              value={form.initial_password}
              onChange={(event) =>
                setForm({ ...form, initial_password: event.target.value })
              }
              helper={t("gyms.initialPasswordHint")}
            />
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={Boolean(created)}
        title={t("athletes.addTitle")}
        onClose={() => setCreated(null)}
        footer={
          <Button onClick={() => setCreated(null)}>{t("common.close")}</Button>
        }
      >
        {created ? (
          <div className="stack-sm">
            <Card>
              <div className="row">
                <Avatar
                  name={
                    created.athlete.profile.full_name ??
                    created.athlete.profile.email
                  }
                />
                <div>
                  <strong>
                    {created.athlete.profile.full_name ??
                      created.athlete.profile.email}
                  </strong>
                  <div className="muted" style={{ fontSize: 11 }}>
                    {created.athlete.coach_name ?? t("athletes.noCoach")}
                  </div>
                </div>
              </div>
            </Card>
            {created.invitation_sent ? (
              <div className="m3-inline-alert m3-inline-alert--info">
                <Mail
                  size={16}
                  style={{ verticalAlign: "middle", marginInlineEnd: 6 }}
                />
                {t("athletes.inviteSent")}
              </div>
            ) : null}
            {created.initial_password ? (
              <>
                <TextField
                  label={t("athletes.initialPassword")}
                  value={created.initial_password}
                  readOnly
                  dir="ltr"
                />
                <Button
                  variant="outlined"
                  icon={<Copy size={16} />}
                  onClick={async () => {
                    await navigator.clipboard.writeText(
                      created.initial_password!,
                    )
                    show(t("common.success"), "success")
                  }}
                >
                  {t("common.copy")}
                </Button>
                <p className="muted" style={{ fontSize: 12 }}>
                  {t("gyms.initialPasswordHint")}
                </p>
              </>
            ) : null}
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
