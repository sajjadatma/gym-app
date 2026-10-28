import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Navigate, useNavigate, useSearch } from "@tanstack/react-router"
import {
  Archive,
  ArrowRightLeft,
  Building2,
  Eye,
  Pencil,
  Phone,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  UserRound,
  Users,
} from "lucide-react"
import { useCallback, useDeferredValue, useEffect, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type AthleteCreated,
  type SuperuserAthleteRow,
  SuperuserAthletesService,
  SuperuserCoachesService,
  type SuperuserCoachRow,
} from "@/client"
import { AsyncPickerField } from "@/components/AsyncPickerField"
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
import { PaginationBar } from "@/components/Pagination"
import {
  PeopleListToolbar,
  type PeopleTab,
  type PeopleView,
} from "@/components/PeopleListToolbar"
import { type RowActionItem, RowActionMenu } from "@/components/RowActionMenu"
import { useI18n } from "@/i18n"
import type { GlobalListSearch, PageSize } from "@/lib/list-search"
import { useServerPage } from "@/lib/server-page"
import { useAsyncPicker } from "@/lib/use-async-picker"
import { useMobileViewport } from "@/lib/useMobileViewport"
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
  const navigate = useNavigate({ from: "/athletes/" })
  const searchParams = useSearch({ from: "/_app/athletes/" })
  const page = searchParams.page ?? 1
  const pageSize = searchParams.size ?? 10
  const searchTerm = searchParams.q ?? ""
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const deferredSearch = useDeferredValue(searchTerm)
  const gymFilter = searchParams.club ?? ""
  const tab: PeopleTab = searchParams.tab ?? "active"
  const [view, setView] = useState<PeopleView>(() => {
    try {
      return localStorage.getItem("superuser.athletes.view") === "table"
        ? "table"
        : "grid"
    } catch {
      return "grid"
    }
  })
  const isMobile = useMobileViewport()
  const activeView = isMobile ? "grid" : view
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<SuperuserAthleteRow | null>(null)
  const [created, setCreated] = useState<AthleteCreated | null>(null)
  const [action, setAction] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({
    full_name: "",
    phone: "",
    coach_user_id: "",
  })
  const [transferTarget, setTransferTarget] =
    useState<SuperuserAthleteRow | null>(null)
  const [transferGymId, setTransferGymId] = useState("")
  const [transferCoachId, setTransferCoachId] = useState("")
  const [transferError, setTransferError] = useState<string | null>(null)
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

  const scope = `${deferredSearch}|${gymFilter}|${tab}`

  const updateListSearch = useCallback(
    (patch: Partial<GlobalListSearch>, replace = false) => {
      void navigate({
        search: (previous) => ({ ...previous, ...patch }),
        replace,
      })
    },
    [navigate],
  )

  const athletesQuery = useQuery({
    queryKey: ["superuser-athletes", scope, page, pageSize],
    queryFn: async () =>
      (
        await SuperuserAthletesService.athletesListAthletes({
          query: {
            q: deferredSearch || undefined,
            gym_id: gymFilter || undefined,
            is_archived: tab === "archived",
            offset: (page - 1) * pageSize,
            limit: pageSize,
          },
        })
      ).data,
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === scope ? previousData : undefined,
  })

  const coachPicker = useAsyncPicker<SuperuserCoachRow>({
    queryKey: ["async-superuser-coaches", form.gym_id],
    enabled: addOpen && Boolean(form.gym_id),
    resetKey: form.gym_id,
    fetchPage: async (search, offset, limit) =>
      (
        await SuperuserCoachesService.coachesListCoaches({
          query: {
            gym_id: form.gym_id,
            is_active: true,
            q: search || undefined,
            offset,
            limit,
          },
        })
      ).data,
  })

  const editCoachPicker = useAsyncPicker<SuperuserCoachRow>({
    queryKey: ["async-superuser-coaches", "edit", editTarget?.gym_id],
    enabled: Boolean(editTarget?.gym_id),
    resetKey: editTarget?.gym_id ?? "",
    fetchPage: async (search, offset, limit) => {
      if (!editTarget) return { data: [], count: 0 }
      return (
        await SuperuserCoachesService.coachesListCoaches({
          query: {
            gym_id: editTarget.gym_id,
            is_active: true,
            q: search || undefined,
            offset,
            limit,
          },
        })
      ).data
    },
  })

  const transferCoachPicker = useAsyncPicker<SuperuserCoachRow>({
    queryKey: ["async-superuser-coaches", "transfer", transferGymId],
    enabled: Boolean(transferGymId),
    resetKey: transferGymId,
    fetchPage: async (search, offset, limit) => {
      if (!transferGymId) return { data: [], count: 0 }
      return (
        await SuperuserCoachesService.coachesListCoaches({
          query: {
            gym_id: transferGymId,
            is_active: true,
            q: search || undefined,
            offset,
            limit,
          },
        })
      ).data
    },
  })

  const rows = athletesQuery.data?.data ?? []
  const total = athletesQuery.data?.count ?? 0
  const setPage = useCallback(
    (next: number, replace = false) =>
      updateListSearch({ page: next }, replace),
    [updateListSearch],
  )
  const { window: pageState, stale } = useServerPage({
    page,
    pageSize,
    total,
    isCurrent: athletesQuery.isSuccess && !athletesQuery.isPlaceholderData,
    onPageChange: setPage,
  })
  const hasFilter = searchTerm.trim().length > 0 || Boolean(gymFilter)

  async function invalidateAll() {
    await queryClient.invalidateQueries({ queryKey: ["superuser-athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["superuser-coaches"] })
    await queryClient.invalidateQueries({ queryKey: ["gyms"] })
    await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["athlete"] })
    await queryClient.invalidateQueries({ queryKey: ["gym"] })
    await queryClient.invalidateQueries({ queryKey: ["members"] })
    await queryClient.invalidateQueries({ queryKey: ["coaches"] })
    await queryClient.invalidateQueries({
      queryKey: ["async-superuser-coaches"],
    })
    await queryClient.invalidateQueries({ queryKey: ["programs"] })
    await queryClient.invalidateQueries({ queryKey: ["program-version"] })
  }

  function openTransfer(row: SuperuserAthleteRow) {
    setTransferTarget(row)
    setTransferGymId("")
    setTransferCoachId("")
    setTransferError(null)
  }

  async function saveTransfer() {
    if (!transferTarget) return
    setTransferError(null)
    if (!transferGymId) {
      setTransferError(t("superuser.destinationGymRequired"))
      return
    }
    if (!transferCoachId) {
      setTransferError(t("superuser.coachRequired"))
      return
    }
    setBusy(true)
    try {
      await SuperuserAthletesService.athletesTransferAthlete({
        path: {
          gym_id: transferTarget.gym_id,
          athlete_user_id: transferTarget.user_id,
        },
        body: {
          gym_id: transferGymId,
          coach_user_id: transferCoachId,
        },
      })
      await invalidateAll()
      setTransferTarget(null)
      show(t("superuser.athleteTransferred"), "success")
    } catch (err) {
      setTransferError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  function openEdit(row: SuperuserAthleteRow) {
    setEditTarget(row)
    setEditForm({
      full_name: row.full_name ?? "",
      phone: row.phone ?? "",
      coach_user_id: row.coach_user_id ?? "",
    })
    setEditError(null)
  }

  async function saveEdit() {
    if (!editTarget) return
    setEditError(null)
    if (!editForm.coach_user_id) {
      setEditError(t("superuser.coachRequired"))
      return
    }
    setBusy(true)
    try {
      await SuperuserAthletesService.athletesUpdateAthlete({
        path: {
          gym_id: editTarget.gym_id,
          athlete_user_id: editTarget.user_id,
        },
        body: {
          full_name: editForm.full_name.trim() || null,
          phone: editForm.phone.trim() || null,
          coach_user_id: editForm.coach_user_id,
        },
      })
      await invalidateAll()
      setEditTarget(null)
      show(t("superuser.athleteUpdated"), "success")
    } catch (err) {
      setEditError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
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
    Boolean(form.gym_id) && !coachPicker.isLoading && coachPicker.total === 0

  function compactRowActions(row: SuperuserAthleteRow) {
    const items: RowActionItem[] = []
    if (!row.is_archived) {
      items.push({
        key: "edit",
        label: t("common.edit"),
        icon: <Pencil size={15} />,
        onSelect: () => openEdit(row),
      })
      items.push({
        key: "transfer",
        label: t("superuser.transferGym"),
        icon: <ArrowRightLeft size={15} />,
        onSelect: () => openTransfer(row),
      })
    }
    items.push({
      key: "archive",
      label: t(row.is_archived ? "superuser.restore" : "superuser.archive"),
      icon: row.is_archived ? <RotateCcw size={15} /> : <Archive size={15} />,
      onSelect: () =>
        setAction({
          kind: row.is_archived ? "restore" : "archive",
          row,
        }),
    })
    if (row.is_archived) {
      items.push({
        key: "delete",
        label: t("common.delete"),
        icon: <Trash2 size={15} />,
        destructive: true,
        separatorBefore: true,
        onSelect: () => setAction({ kind: "delete", row }),
      })
    }
    return (
      <div className="m3-row-actions">
        <Button
          variant="text"
          size="sm"
          icon={<Eye size={14} />}
          onClick={() =>
            navigate({
              to: "/people/$userId",
              params: { userId: row.user_id },
              search: { gym: row.gym_id, kind: "ATHLETE" },
            })
          }
        >
          {t("common.details")}
        </Button>
        <RowActionMenu
          items={items}
          label={t("common.moreActions")}
          disabled={stale}
        />
      </div>
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
        search={searchTerm}
        onSearch={(value) => updateListSearch({ q: value, page: 1 }, true)}
        searchLabel={t("athletes.search")}
        clearSearchLabel={t("athletes.clearSearch")}
        countLabel={t("athletes.countLabel", {
          count: formatNumber(total),
        })}
        view={activeView}
        onViewChange={setView}
        viewLabel={t("athletes.view")}
        gridLabel={t("athletes.gridView")}
        tableLabel={t("athletes.tableView")}
        clubValue={gymFilter}
        onClubChange={(value) => updateListSearch({ club: value, page: 1 })}
        clubLabel={t("superuser.club")}
        clubOptions={[
          { value: "", label: t("superuser.allClubs") },
          ...gymOptions,
        ]}
        tab={tab}
        onTabChange={(value) => updateListSearch({ tab: value, page: 1 })}
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
                onClick={() =>
                  updateListSearch({ q: "", club: "", page: 1 }, true)
                }
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
      ) : activeView === "grid" ? (
        <div
          className={`m3-card-grid ${stale ? "is-updating" : ""}`}
          aria-busy={stale}
        >
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
                <div className="m3-entity-card__actions">
                  {compactRowActions(row)}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Card className="m3-data-card">
          <div
            className={`m3-table-wrap m3-data-table-wrap ${
              stale ? "is-updating" : ""
            }`}
            aria-busy={stale}
          >
            <table className="m3-table m3-data-table m3-people-table m3-people-table--athletes">
              <thead>
                <tr>
                  <th scope="col" className="m3-people-table__person">
                    {t("athletes.athlete")}
                  </th>
                  <th scope="col" className="m3-people-table__club">
                    {t("superuser.club")}
                  </th>
                  <th scope="col" className="m3-people-table__coach">
                    {t("members.coach")}
                  </th>
                  <th scope="col" className="m3-people-table__phone">
                    {t("profile.phone")}
                  </th>
                  <th scope="col" className="m3-people-table__status">
                    {t("superuser.status")}
                  </th>
                  <th scope="col" className="m3-people-table__actions">
                    {t("common.actions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.gym_id}:${row.user_id}`}>
                    <td>
                      <div className="row" style={{ gap: 10 }}>
                        <Avatar name={row.full_name ?? row.email} />
                        <div className="m3-data-table__person">
                          <strong
                            className="truncate"
                            title={row.full_name ?? row.email}
                          >
                            {row.full_name ?? row.email}
                          </strong>
                          <span
                            dir="ltr"
                            className="m3-data-table__email truncate"
                            title={row.email}
                          >
                            {row.email}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="m3-people-table__club">
                      <span title={row.gym_name}>{row.gym_name}</span>
                    </td>
                    <td className="m3-people-table__coach">
                      <span title={row.coach_name ?? t("athletes.noCoach")}>
                        {row.coach_name ?? t("athletes.noCoach")}
                      </span>
                    </td>
                    <td dir="ltr" className="m3-people-table__phone">
                      {row.phone || "—"}
                    </td>
                    <td className="m3-people-table__status">
                      <StatusBadge
                        status={row.is_archived ? "archived" : "active"}
                      />
                    </td>
                    <td className="m3-people-table__actions">
                      {compactRowActions(row)}
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
          pageSize={pageSize}
          total={pageState.total}
          start={pageState.start}
          end={pageState.end}
          loading={stale || athletesQuery.isFetching}
          onPageChange={setPage}
          onPageSizeChange={(size) =>
            updateListSearch({ size: size as PageSize, page: 1 })
          }
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
          <AsyncPickerField
            label={t("members.coach")}
            value={form.coach_user_id}
            onChange={(value) => setForm({ ...form, coach_user_id: value })}
            picker={coachPicker}
            getOption={(coach) => ({
              value: coach.user_id,
              label: coach.full_name ?? coach.email,
            })}
            helper={noCoach ? t("superuser.noCoachForGym") : undefined}
            placeholder={t("athletes.chooseCoach")}
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

      <Dialog
        open={Boolean(editTarget)}
        title={t("superuser.editAthlete")}
        description={editTarget?.email}
        onClose={() => {
          if (busy) return
          setEditTarget(null)
          setEditError(null)
        }}
        footer={
          <>
            <Button
              variant="text"
              disabled={busy}
              onClick={() => {
                setEditTarget(null)
                setEditError(null)
              }}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={saveEdit}
              loading={busy}
              disabled={!editForm.coach_user_id}
            >
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <div className="m3-inline-alert m3-inline-alert--info">
            {t("superuser.athleteEditScopeHint", {
              gym: editTarget?.gym_name ?? "",
            })}
          </div>
          {editError ? (
            <div className="m3-inline-alert" role="alert">
              {editError}
            </div>
          ) : null}
          <TextField
            label={t("athletes.fullName")}
            value={editForm.full_name}
            onChange={(event) =>
              setEditForm({ ...editForm, full_name: event.target.value })
            }
          />
          <TextField
            label={t("profile.phone")}
            type="tel"
            dir="ltr"
            value={editForm.phone}
            onChange={(event) =>
              setEditForm({ ...editForm, phone: event.target.value })
            }
          />
          <AsyncPickerField
            label={t("members.coach")}
            value={editForm.coach_user_id}
            onChange={(value) =>
              setEditForm({ ...editForm, coach_user_id: value })
            }
            picker={editCoachPicker}
            getOption={(coach) => ({
              value: coach.user_id,
              label: coach.full_name ?? coach.email,
            })}
            selectedLabel={editTarget?.coach_name ?? ""}
            placeholder={t("athletes.chooseCoach")}
            required
          />
          <TextField
            label={t("auth.email")}
            value={editTarget?.email ?? ""}
            dir="ltr"
            readOnly
          />
          <p className="muted">{editTarget?.gym_name}</p>
        </div>
      </Dialog>

      <Dialog
        open={Boolean(transferTarget)}
        title={t("superuser.transferAthlete")}
        description={transferTarget?.email}
        onClose={() => {
          if (busy) return
          setTransferTarget(null)
          setTransferError(null)
        }}
        footer={
          <>
            <Button
              variant="text"
              disabled={busy}
              onClick={() => {
                setTransferTarget(null)
                setTransferError(null)
              }}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={saveTransfer}
              loading={busy}
              disabled={!transferGymId || !transferCoachId}
            >
              {t("superuser.transferAction")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <div className="m3-inline-alert m3-inline-alert--info">
            {t("superuser.transferAthleteHint")}
          </div>
          {transferError ? (
            <div className="m3-inline-alert" role="alert">
              {transferError}
            </div>
          ) : null}
          <p className="muted">
            {t("superuser.currentGym", {
              gym: transferTarget?.gym_name ?? "",
            })}
          </p>
          <SelectField
            label={t("superuser.destinationGym")}
            value={transferGymId}
            onChange={(value) => {
              setTransferGymId(value)
              setTransferCoachId("")
            }}
            options={gymOptions.filter(
              (option) => option.value !== transferTarget?.gym_id,
            )}
            required
          />
          <AsyncPickerField
            label={t("members.coach")}
            value={transferCoachId}
            onChange={(value) => setTransferCoachId(value)}
            picker={transferCoachPicker}
            getOption={(coach) => ({
              value: coach.user_id,
              label: coach.full_name ?? coach.email,
            })}
            placeholder={t("athletes.chooseCoach")}
            helper={t("superuser.transferCoachHintShort")}
            required
          />
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
