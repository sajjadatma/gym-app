import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Navigate } from "@tanstack/react-router"
import {
  Archive,
  Building2,
  Phone,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  Users,
} from "lucide-react"
import { useDeferredValue, useEffect, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type SuperuserCoachCreated,
  SuperuserCoachesService,
  type SuperuserCoachRow,
} from "@/client"
import {
  Avatar,
  Button,
  Card,
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
import {
  PeopleListToolbar,
  type PeopleTab,
  type PeopleView,
} from "@/components/PeopleListToolbar"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

type Action = {
  kind: "archive" | "restore" | "delete"
  row: SuperuserCoachRow
}

export function SuperuserCoachesPage() {
  const { isSuperuser, activeGymId } = useAuth()
  if (activeGymId) {
    return (
      <Navigate
        to="/gyms/$gymId/members"
        params={{ gymId: activeGymId }}
        replace
      />
    )
  }
  if (!isSuperuser) return <Navigate to="/" replace />
  return <CoachesContent />
}

function CoachesContent() {
  const { t, formatNumber, formatDate } = useI18n()
  const { gyms } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)
  const [gymFilter, setGymFilter] = useState("")
  const [tab, setTab] = useState<PeopleTab>("active")
  const [view, setView] = useState<PeopleView>(() => {
    try {
      return localStorage.getItem("superuser.coaches.view") === "table"
        ? "table"
        : "grid"
    } catch {
      return "grid"
    }
  })
  const [addOpen, setAddOpen] = useState(false)
  const [created, setCreated] = useState<SuperuserCoachCreated | null>(null)
  const [action, setAction] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    gym_id: "",
    email: "",
    full_name: "",
    phone: "",
    activation_method: "invite" as "invite" | "password",
    initial_password: "",
  })

  useEffect(() => {
    try {
      localStorage.setItem("superuser.coaches.view", view)
    } catch {
      // Storage may be unavailable; the in-memory view still works.
    }
  }, [view])

  const coachesQuery = useQuery({
    queryKey: ["superuser-coaches", deferredSearch, gymFilter],
    queryFn: async () =>
      (
        await SuperuserCoachesService.coachesListCoaches({
          query: {
            q: deferredSearch || undefined,
            gym_id: gymFilter || undefined,
            include_archived: true,
          },
        })
      ).data,
  })

  const allRows = coachesQuery.data?.data ?? []
  const rows = allRows.filter((row) =>
    tab === "archived" ? !row.is_active : row.is_active,
  )
  const hasFilter = search.trim().length > 0 || Boolean(gymFilter)

  async function createCoach() {
    setError(null)
    if (!form.gym_id) {
      setError(t("validation.required"))
      return
    }
    if (!/^\S+@\S+\.\S+$/.test(form.email)) {
      setError(t("validation.email"))
      return
    }
    if (!form.phone.trim()) {
      setError(t("validation.coachPhone"))
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
      const response = await SuperuserCoachesService.coachesCreateCoach({
        body: {
          gym_id: form.gym_id,
          email: form.email,
          full_name: form.full_name || null,
          phone: form.phone.trim(),
          activation_method: form.activation_method,
          initial_password:
            form.activation_method === "password"
              ? form.initial_password || null
              : null,
        },
      })
      await invalidateAll()
      setAddOpen(false)
      setCreated(response.data)
      setForm({
        gym_id: form.gym_id,
        email: "",
        full_name: "",
        phone: "",
        activation_method: "invite",
        initial_password: "",
      })
      show(t("superuser.createdCoach"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  async function invalidateAll() {
    await queryClient.invalidateQueries({ queryKey: ["superuser-coaches"] })
    await queryClient.invalidateQueries({ queryKey: ["gyms"] })
    await queryClient.invalidateQueries({ queryKey: ["members"] })
    await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["athlete"] })
    await queryClient.invalidateQueries({ queryKey: ["gym"] })
  }

  async function runAction() {
    if (!action) return
    setBusy(true)
    try {
      if (action.kind === "archive") {
        await SuperuserCoachesService.coachesArchiveCoach({
          path: { membership_id: action.row.membership_id },
        })
      } else if (action.kind === "restore") {
        await SuperuserCoachesService.coachesRestoreCoach({
          path: { membership_id: action.row.membership_id },
        })
      } else {
        await SuperuserCoachesService.coachesDeleteCoach({
          path: { membership_id: action.row.membership_id },
        })
      }
      await invalidateAll()
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

  function rowActions(row: SuperuserCoachRow) {
    return (
      <>
        {row.can_archive ? (
          <Button
            variant="text"
            size="sm"
            icon={
              row.is_active ? <Archive size={14} /> : <RotateCcw size={14} />
            }
            onClick={() =>
              setAction({
                kind: row.is_active ? "archive" : "restore",
                row,
              })
            }
          >
            {t(row.is_active ? "superuser.archive" : "superuser.restore")}
          </Button>
        ) : null}
        <Button
          variant="text"
          size="sm"
          icon={<Trash2 size={14} />}
          onClick={() => setAction({ kind: "delete", row })}
        >
          {t("common.delete")}
        </Button>
      </>
    )
  }

  function statusOf(row: SuperuserCoachRow) {
    return row.is_active ? "active" : "archived"
  }

  return (
    <>
      <PageHeader
        title={t("superuser.coaches")}
        subtitle={t("superuser.coachesSubtitle")}
        actions={
          <Button icon={<Plus size={17} />} onClick={() => setAddOpen(true)}>
            {t("superuser.addCoach")}
          </Button>
        }
      />

      <PeopleListToolbar
        search={search}
        onSearch={setSearch}
        searchLabel={t("athletes.search")}
        clearSearchLabel={t("athletes.clearSearch")}
        countLabel={t("superuser.coachCountLabel", {
          count: formatNumber(rows.length),
        })}
        view={view}
        onViewChange={setView}
        viewLabel={t("athletes.view")}
        gridLabel={t("athletes.gridView")}
        tableLabel={t("athletes.tableView")}
        clubValue={gymFilter}
        onClubChange={setGymFilter}
        clubLabel={t("superuser.club")}
        clubOptions={[
          { value: "", label: t("superuser.allClubs") },
          ...gymOptions,
        ]}
        tab={tab}
        onTabChange={setTab}
        tabLabel={t("superuser.coaches")}
        activeLabel={t("status.active")}
        archivedLabel={t("status.archived")}
      />

      {coachesQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : coachesQuery.isError ? (
        <ErrorState
          message={translateApiError(coachesQuery.error, t)}
          retryLabel={t("common.retry")}
          onRetry={() => coachesQuery.refetch()}
        />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={hasFilter ? <Search size={26} /> : <Users size={26} />}
          title={hasFilter ? t("common.noResults") : t("superuser.noCoaches")}
          description={
            hasFilter
              ? t("athletes.noResultsHint")
              : t("superuser.emptyCoachHint")
          }
          action={
            hasFilter ? (
              <Button
                variant="outlined"
                onClick={() => {
                  setSearch("")
                  setGymFilter("")
                }}
              >
                {t("athletes.clearSearch")}
              </Button>
            ) : (
              <Button
                icon={<Plus size={17} />}
                onClick={() => setAddOpen(true)}
              >
                {t("superuser.addCoach")}
              </Button>
            )
          }
        />
      ) : view === "grid" ? (
        <div className="m3-card-grid">
          {rows.map((row) => (
            <div
              key={row.membership_id}
              className={`m3-entity-card ${row.is_active ? "" : "is-archived"}`}
            >
              <div className="m3-entity-card__body">
                <div className="m3-entity-card__head">
                  <div className="m3-entity-card__identity">
                    <Avatar name={row.full_name ?? row.email} />
                    <div className="m3-entity-card__person">
                      <div
                        className="m3-entity-card__title"
                        title={row.full_name ?? row.email}
                      >
                        {row.full_name ?? row.email}
                      </div>
                      <div
                        className="m3-entity-card__email truncate"
                        dir="ltr"
                        title={row.email}
                      >
                        {row.email}
                      </div>
                    </div>
                  </div>
                  <StatusBadge status={statusOf(row)} />
                </div>
                <div className="m3-entity-card__meta">
                  <span>
                    <Building2 size={13} aria-hidden /> {row.gym_name}
                  </span>
                  <span dir="ltr">
                    <Phone size={13} aria-hidden /> {row.phone || "—"}
                  </span>
                  <span className="muted">{formatDate(row.created_at)}</span>
                </div>
              </div>
              <div className="m3-entity-card__footer">
                <div className="m3-entity-card__actions">{rowActions(row)}</div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Card className="m3-data-card">
          <div className="m3-table-wrap m3-data-table-wrap">
            <table className="m3-table m3-data-table">
              <thead>
                <tr>
                  <th scope="col">{t("athletes.fullName")}</th>
                  <th scope="col">{t("profile.phone")}</th>
                  <th scope="col">{t("superuser.club")}</th>
                  <th scope="col">{t("superuser.status")}</th>
                  <th scope="col">{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.membership_id}>
                    <td>
                      <div className="row" style={{ gap: 10 }}>
                        <Avatar name={row.full_name ?? row.email} />
                        <div className="m3-data-table__person">
                          <strong>{row.full_name ?? row.email}</strong>
                          <span dir="ltr">{row.email}</span>
                        </div>
                      </div>
                    </td>
                    <td dir="ltr" className="m3-data-table__num">
                      {row.phone || "—"}
                    </td>
                    <td>{row.gym_name}</td>
                    <td>
                      <StatusBadge status={statusOf(row)} />
                    </td>
                    <td>
                      <div
                        className="row"
                        style={{ gap: 4, flexWrap: "nowrap" }}
                      >
                        {rowActions(row)}
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
        title={t("superuser.addCoach")}
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
            <Button onClick={createCoach} loading={busy}>
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
            onChange={(value) => setForm({ ...form, gym_id: value })}
            options={gymOptions}
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
            required
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

      <CreateResultDialog created={created} onClose={() => setCreated(null)} />

      <ConfirmDialog
        open={Boolean(action)}
        title={t(
          action?.kind === "delete"
            ? "superuser.deleteCoachTitle"
            : action?.kind === "restore"
              ? "superuser.restoreTitle"
              : "superuser.archiveCoachTitle",
        )}
        description={t(
          action?.kind === "delete"
            ? "superuser.deleteCoachBody"
            : action?.kind === "restore"
              ? "superuser.restoreBody"
              : "superuser.archiveCoachBody",
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

function CreateResultDialog({
  created,
  onClose,
}: {
  created: SuperuserCoachCreated | null
  onClose: () => void
}) {
  const { t } = useI18n()
  if (!created) return null
  return (
    <Dialog
      open
      title={t("superuser.createdCoach")}
      onClose={onClose}
      footer={<Button onClick={onClose}>{t("common.close")}</Button>}
    >
      <div className="stack-sm">
        <strong>{created.coach.full_name ?? created.coach.email}</strong>
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
