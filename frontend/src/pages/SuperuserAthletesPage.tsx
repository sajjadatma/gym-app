import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Navigate } from "@tanstack/react-router"
import { Archive, Plus, RotateCcw, Search, Trash2 } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type AthleteCreated,
  type SuperuserAthleteRow,
  SuperuserAthletesService,
  SuperuserCoachesService,
} from "@/client"
import {
  Avatar,
  Button,
  Card,
  Chip,
  ConfirmDialog,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  SelectField,
  Spinner,
  StatusBadge,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

type Action = {
  kind: "archive" | "restore" | "delete"
  row: SuperuserAthleteRow
}

export function SuperuserAthletesPage() {
  const { isSuperuser, activeGymId } = useAuth()
  if (activeGymId) {
    return (
      <Navigate
        to="/gyms/$gymId/athletes"
        params={{ gymId: activeGymId }}
        replace
      />
    )
  }
  if (!isSuperuser) return <Navigate to="/" replace />
  return <AthletesContent />
}

function AthletesContent() {
  const { t, formatDate } = useI18n()
  const { gyms } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [q, setQ] = useState("")
  const [gymFilter, setGymFilter] = useState("")
  const [includeArchived, setIncludeArchived] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [created, setCreated] = useState<AthleteCreated | null>(null)
  const [action, setAction] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    gym_id: "",
    coach_user_id: "",
    email: "",
    full_name: "",
    phone: "",
    activation_method: "invite" as "invite" | "password",
    initial_password: "",
  })

  const athletesQuery = useQuery({
    queryKey: ["superuser-athletes", q, gymFilter, includeArchived],
    queryFn: async () =>
      (
        await SuperuserAthletesService.athletesListAthletes({
          query: {
            q: q || undefined,
            gym_id: gymFilter || undefined,
            include_archived: includeArchived,
          },
        })
      ).data,
  })

  const coachOptionsQuery = useQuery({
    queryKey: ["superuser-coaches", form.gym_id, "athlete-options"],
    queryFn: async () =>
      (
        await SuperuserCoachesService.coachesListCoaches({
          query: { gym_id: form.gym_id, include_archived: false },
        })
      ).data.data,
    enabled: Boolean(form.gym_id),
  })
  const coachOptions = (coachOptionsQuery.data ?? []).map((coach) => ({
    value: coach.user_id,
    label: coach.full_name ?? coach.email,
  }))

  async function createAthlete() {
    setError(null)
    if (!form.gym_id) {
      setError(t("validation.required"))
      return
    }
    if (!form.coach_user_id) {
      setError(t("superuser.coachRequired"))
      return
    }
    if (!/^\S+@\S+\.\S+$/.test(form.email)) {
      setError(t("validation.email"))
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
    setBusy(true)
    try {
      const response = await SuperuserAthletesService.athletesCreateAthlete({
        body: {
          gym_id: form.gym_id,
          coach_user_id: form.coach_user_id,
          email: form.email,
          full_name: form.full_name || null,
          phone: form.phone.trim() || null,
          activation_method: form.activation_method,
          initial_password:
            form.activation_method === "password"
              ? form.initial_password || null
              : null,
        },
      })
      await queryClient.invalidateQueries({ queryKey: ["superuser-athletes"] })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      setAddOpen(false)
      setCreated(response.data)
      setForm({
        gym_id: form.gym_id,
        coach_user_id: form.coach_user_id,
        email: "",
        full_name: "",
        phone: "",
        activation_method: "invite",
        initial_password: "",
      })
      show(t("superuser.createdAthlete"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  async function runAction() {
    if (!action) return
    setBusy(true)
    try {
      const path = {
        gym_id: action.row.gym_id,
        athlete_user_id: action.row.user_id,
      }
      if (action.kind === "archive") {
        await SuperuserAthletesService.athletesArchiveAthlete({ path })
      } else if (action.kind === "restore") {
        await SuperuserAthletesService.athletesRestoreAthlete({ path })
      } else {
        await SuperuserAthletesService.athletesDeleteAthlete({ path })
      }
      await queryClient.invalidateQueries({ queryKey: ["superuser-athletes"] })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      show(
        t(
          action.kind === "archive"
            ? "superuser.archived"
            : action.kind === "restore"
              ? "superuser.restored"
              : "superuser.deleted",
        ),
        "success",
      )
      setAction(null)
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setBusy(false)
    }
  }

  const gymOptions = gyms.map((gym) => ({
    value: gym.id,
    label: gym.name,
  }))
  const noCoach =
    Boolean(form.gym_id) &&
    !coachOptionsQuery.isLoading &&
    coachOptions.length === 0

  return (
    <>
      <PageHeader
        title={t("superuser.athletes")}
        subtitle={t("superuser.athletesSubtitle")}
        actions={
          <Button icon={<Plus size={17} />} onClick={() => setAddOpen(true)}>
            {t("superuser.addAthlete")}
          </Button>
        }
      />

      <Card className="m3-card--outlined">
        <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 240px" }}>
            <TextField
              label={t("superuser.search")}
              value={q}
              onChange={(event) => setQ(event.target.value)}
              leading={<Search size={16} />}
            />
          </div>
          <div style={{ flex: "0 1 220px" }}>
            <SelectField
              label={t("superuser.club")}
              value={gymFilter}
              onChange={setGymFilter}
              options={[
                { value: "", label: t("superuser.allClubs") },
                ...gymOptions,
              ]}
            />
          </div>
          <Chip
            selected={includeArchived}
            onClick={() => setIncludeArchived((value) => !value)}
          >
            {t("superuser.showArchived")}
          </Chip>
        </div>
      </Card>

      {athletesQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : athletesQuery.isError ? (
        <ErrorState
          message={translateApiError(athletesQuery.error, t)}
          retryLabel={t("common.retry")}
          onRetry={() => athletesQuery.refetch()}
        />
      ) : (athletesQuery.data?.data.length ?? 0) === 0 ? (
        <EmptyState
          title={t("superuser.noAthletes")}
          description={t("superuser.emptyAthleteHint")}
          action={
            <Button icon={<Plus size={17} />} onClick={() => setAddOpen(true)}>
              {t("superuser.addAthlete")}
            </Button>
          }
        />
      ) : (
        <Card className="m3-card--outlined">
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("athletes.fullName")}</th>
                  <th>{t("auth.email")}</th>
                  <th>{t("profile.phone")}</th>
                  <th>{t("superuser.club")}</th>
                  <th>{t("members.coach")}</th>
                  <th>{t("superuser.status")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {athletesQuery.data?.data.map((row) => (
                  <tr key={`${row.gym_id}:${row.user_id}`}>
                    <td>
                      <div className="row" style={{ gap: 10 }}>
                        <Avatar name={row.full_name ?? row.email} />
                        <div>
                          <div style={{ fontWeight: 650 }}>
                            {row.full_name ?? row.email}
                          </div>
                          <div className="muted" style={{ fontSize: 10.5 }}>
                            {formatDate(row.created_at)}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td dir="ltr" style={{ textAlign: "start" }}>
                      {row.email}
                    </td>
                    <td dir="ltr" style={{ textAlign: "start" }}>
                      {row.phone || "—"}
                    </td>
                    <td>{row.gym_name}</td>
                    <td>{row.coach_name ?? "—"}</td>
                    <td>
                      <StatusBadge
                        status={row.is_archived ? "archived" : "active"}
                      />
                    </td>
                    <td>
                      <div
                        className="row"
                        style={{ gap: 4, flexWrap: "nowrap" }}
                      >
                        <Button
                          variant="text"
                          size="sm"
                          icon={
                            row.is_archived ? (
                              <RotateCcw size={14} />
                            ) : (
                              <Archive size={14} />
                            )
                          }
                          onClick={() =>
                            setAction({
                              kind: row.is_archived ? "restore" : "archive",
                              row,
                            })
                          }
                        >
                          {t(
                            row.is_archived
                              ? "superuser.restore"
                              : "superuser.archive",
                          )}
                        </Button>
                        <Button
                          variant="text"
                          size="sm"
                          icon={<Trash2 size={14} />}
                          onClick={() => setAction({ kind: "delete", row })}
                        >
                          {t("common.delete")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Dialog
        open={addOpen}
        title={t("superuser.addAthlete")}
        onClose={() => {
          setAddOpen(false)
          setError(null)
        }}
        footer={
          <>
            <Button
              variant="text"
              onClick={() => {
                setAddOpen(false)
                setError(null)
              }}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={createAthlete} loading={busy} disabled={noCoach}>
              {t("common.create")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <SelectField
            label={t("superuser.club")}
            value={form.gym_id}
            onChange={(value) =>
              setForm({ ...form, gym_id: value, coach_user_id: "" })
            }
            options={gymOptions}
            required
          />
          <SelectField
            label={t("members.coach")}
            value={form.coach_user_id}
            onChange={(value) => setForm({ ...form, coach_user_id: value })}
            options={coachOptions}
            helper={noCoach ? t("superuser.noCoachForGym") : undefined}
            disabled={!form.gym_id || coachOptionsQuery.isLoading || noCoach}
            required
          />
          <TextField
            label={t("athletes.fullName")}
            value={form.full_name}
            onChange={(event) =>
              setForm({ ...form, full_name: event.target.value })
            }
          />
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
            label={t("profile.phone")}
            type="tel"
            dir="ltr"
            value={form.phone}
            onChange={(event) =>
              setForm({ ...form, phone: event.target.value })
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

      <CreateAthleteResultDialog
        created={created}
        onClose={() => setCreated(null)}
      />

      <ConfirmDialog
        open={Boolean(action)}
        title={t(
          action?.kind === "delete"
            ? "superuser.deleteAthleteTitle"
            : action?.kind === "restore"
              ? "superuser.restoreTitle"
              : "superuser.archiveAthleteTitle",
        )}
        description={t(
          action?.kind === "delete"
            ? "superuser.deleteAthleteBody"
            : action?.kind === "restore"
              ? "superuser.restoreBody"
              : "superuser.archiveAthleteBody",
        )}
        confirmLabel={t(
          action?.kind === "delete"
            ? "common.delete"
            : action?.kind === "restore"
              ? "superuser.restore"
              : "superuser.archive",
        )}
        cancelLabel={t("common.cancel")}
        destructive={action?.kind === "delete"}
        loading={busy}
        onConfirm={runAction}
        onClose={() => setAction(null)}
      />
    </>
  )
}

function CreateAthleteResultDialog({
  created,
  onClose,
}: {
  created: AthleteCreated | null
  onClose: () => void
}) {
  const { t } = useI18n()
  if (!created) return null
  return (
    <Dialog
      open
      title={t("superuser.createdAthlete")}
      onClose={onClose}
      footer={<Button onClick={onClose}>{t("common.close")}</Button>}
    >
      <div className="stack-sm">
        <strong>
          {created.athlete.profile.full_name ?? created.athlete.profile.email}
        </strong>
        {created.invitation_sent ? (
          <div className="m3-inline-alert m3-inline-alert--info">
            {t("gyms.invitationSent")}
          </div>
        ) : null}
        {created.initial_password ? (
          <TextField
            label={t("gyms.initialPassword")}
            value={created.initial_password}
            readOnly
            dir="ltr"
          />
        ) : null}
      </div>
    </Dialog>
  )
}
