import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { Navigate } from "@tanstack/react-router"
import {
  Archive,
  Building2,
  Phone,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  UserRound,
  Users,
} from "lucide-react"
import { useDeferredValue, useEffect, useState } from "react"
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
import { PaginationBar, pageWindow, usePager } from "@/components/Pagination"
import {
  PeopleListToolbar,
  type PeopleTab,
  type PeopleView,
} from "@/components/PeopleListToolbar"
import { useI18n } from "@/i18n"
import { fetchAllPages } from "@/lib/fetch-all-pages"
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
      return localStorage.getItem("superuser.athletes.view") === "table"
        ? "table"
        : "grid"
    } catch {
      return "grid"
    }
  })
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

  useEffect(() => {
    try {
      localStorage.setItem("superuser.athletes.view", view)
    } catch {
      // Storage may be unavailable; the in-memory view still works.
    }
  }, [view])

  const resetKey = `${deferredSearch}|${gymFilter}|${tab}`
  const pager = usePager(resetKey)

  const athletesQuery = useQuery({
    queryKey: [
      "superuser-athletes",
      deferredSearch,
      gymFilter,
      tab,
      pager.offset,
      pager.limit,
    ],
    queryFn: async () =>
      (
        await SuperuserAthletesService.athletesListAthletes({
          query: {
            q: deferredSearch || undefined,
            gym_id: gymFilter || undefined,
            is_archived: tab === "archived",
            offset: pager.offset,
            limit: pager.limit,
          },
        })
      ).data,
    placeholderData: keepPreviousData,
  })

  const coachOptionsQuery = useQuery({
    queryKey: ["superuser-coaches", form.gym_id, "athlete-options"],
    queryFn: async () =>
      // Every coach in the club must be reachable in the picker.
      fetchAllPages(async (offset, limit) => {
        const response = await SuperuserCoachesService.coachesListCoaches({
          query: {
            gym_id: form.gym_id,
            is_active: true,
            offset,
            limit,
          },
        })
        return response.data
      }),
    enabled: Boolean(form.gym_id),
  })
  const coachOptions = (coachOptionsQuery.data ?? []).map((coach) => ({
    value: coach.user_id,
    label: coach.full_name ?? coach.email,
  }))

  const rows = athletesQuery.data?.data ?? []
  const total = athletesQuery.data?.count ?? 0
  const pageState = pageWindow(pager, total)
  if (pager.page !== pageState.page) pager.setPage(pageState.page)
  const hasFilter = search.trim().length > 0 || Boolean(gymFilter)

  async function invalidateAll() {
    await queryClient.invalidateQueries({ queryKey: ["superuser-athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["gyms"] })
    await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["athlete"] })
    await queryClient.invalidateQueries({ queryKey: ["gym"] })
  }

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
      await invalidateAll()
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
  const noCoach =
    Boolean(form.gym_id) &&
    !coachOptionsQuery.isLoading &&
    coachOptions.length === 0

  function rowActions(row: SuperuserAthleteRow) {
    return (
      <>
        <Button
          variant="text"
          size="sm"
          icon={
            row.is_archived ? <RotateCcw size={14} /> : <Archive size={14} />
          }
          onClick={() =>
            setAction({
              kind: row.is_archived ? "restore" : "archive",
              row,
            })
          }
        >
          {t(row.is_archived ? "superuser.restore" : "superuser.archive")}
        </Button>
        {row.is_archived ? (
          <Button
            variant="text"
            size="sm"
            icon={<Trash2 size={14} />}
            onClick={() => setAction({ kind: "delete", row })}
          >
            {t("common.delete")}
          </Button>
        ) : null}
      </>
    )
  }

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

      <PeopleListToolbar
        search={search}
        onSearch={setSearch}
        searchLabel={t("athletes.search")}
        clearSearchLabel={t("athletes.clearSearch")}
        countLabel={t("athletes.countLabel", {
          count: formatNumber(total),
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
        tabLabel={t("superuser.athletes")}
        activeLabel={t("status.active")}
        archivedLabel={t("status.archived")}
      />

      {athletesQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : athletesQuery.isError ? (
        <ErrorState
          message={translateApiError(athletesQuery.error, t)}
          retryLabel={t("common.retry")}
          onRetry={() => athletesQuery.refetch()}
        />
      ) : total === 0 ? (
        <EmptyState
          icon={hasFilter ? <Search size={26} /> : <Users size={26} />}
          title={hasFilter ? t("common.noResults") : t("superuser.noAthletes")}
          description={
            hasFilter
              ? t("athletes.noResultsHint")
              : t("superuser.emptyAthleteHint")
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
                {t("superuser.addAthlete")}
              </Button>
            )
          }
        />
      ) : view === "grid" ? (
        <div className="m3-card-grid">
          {rows.map((row) => (
            <div
              key={`${row.gym_id}:${row.user_id}`}
              className={`m3-entity-card ${row.is_archived ? "is-archived" : ""}`}
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
                  <StatusBadge
                    status={row.is_archived ? "archived" : "active"}
                  />
                </div>
                <div className="m3-entity-card__meta">
                  <span>
                    <Building2 size={13} aria-hidden /> {row.gym_name}
                  </span>
                  <span>
                    <UserRound size={13} aria-hidden />{" "}
                    {row.coach_name ?? t("athletes.noCoach")}
                  </span>
                  {row.phone ? (
                    <span dir="ltr">
                      <Phone size={13} aria-hidden /> {row.phone}
                    </span>
                  ) : null}
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
                  <th scope="col">{t("athletes.athlete")}</th>
                  <th scope="col">{t("superuser.club")}</th>
                  <th scope="col">{t("members.coach")}</th>
                  <th scope="col">{t("profile.phone")}</th>
                  <th scope="col">{t("superuser.status")}</th>
                  <th scope="col">{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.gym_id}:${row.user_id}`}>
                    <td>
                      <div className="row" style={{ gap: 10 }}>
                        <Avatar name={row.full_name ?? row.email} />
                        <div className="m3-data-table__person">
                          <strong>{row.full_name ?? row.email}</strong>
                          <span dir="ltr">{row.email}</span>
                        </div>
                      </div>
                    </td>
                    <td>{row.gym_name}</td>
                    <td>{row.coach_name ?? t("athletes.noCoach")}</td>
                    <td dir="ltr" className="m3-data-table__num">
                      {row.phone || "—"}
                    </td>
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

      {total > 0 ? (
        <PaginationBar
          page={pageState.page}
          pageCount={pageState.pageCount}
          pageSize={pager.pageSize}
          total={pageState.total}
          start={pageState.start}
          end={pageState.end}
          loading={athletesQuery.isFetching}
          onPageChange={pager.setPage}
          onPageSizeChange={pager.setPageSize}
        />
      ) : null}

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
