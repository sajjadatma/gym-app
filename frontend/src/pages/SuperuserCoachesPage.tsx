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
  UserMinus,
  Users,
} from "lucide-react"
import { useCallback, useDeferredValue, useEffect, useState } from "react"
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
import { PaginationBar } from "@/components/Pagination"
import {
  PeopleListToolbar,
  type PeopleTab,
  type PeopleView,
} from "@/components/PeopleListToolbar"
import { useI18n } from "@/i18n"
import type { GlobalListSearch, PageSize } from "@/lib/list-search"
import { useServerPage } from "@/lib/server-page"
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
  const navigate = useNavigate({ from: "/coaches" })
  const searchParams = useSearch({ from: "/_app/coaches" })
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
      return localStorage.getItem("superuser.coaches.view") === "table"
        ? "table"
        : "grid"
    } catch {
      return "grid"
    }
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<SuperuserCoachRow | null>(null)
  const [created, setCreated] = useState<SuperuserCoachCreated | null>(null)
  const [action, setAction] = useState<Action | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ full_name: "", phone: "" })
  const [transferTarget, setTransferTarget] =
    useState<SuperuserCoachRow | null>(null)
  const [transferGymId, setTransferGymId] = useState("")
  const [transferError, setTransferError] = useState<string | null>(null)
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

  const coachesQuery = useQuery({
    queryKey: ["superuser-coaches", scope, page, pageSize],
    queryFn: async () =>
      (
        await SuperuserCoachesService.coachesListCoaches({
          query: {
            q: deferredSearch || undefined,
            gym_id: gymFilter || undefined,
            is_active: tab === "active",
            offset: (page - 1) * pageSize,
            limit: pageSize,
          },
        })
      ).data,
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === scope ? previousData : undefined,
  })

  const rows = coachesQuery.data?.data ?? []
  const total = coachesQuery.data?.count ?? 0
  const setPage = useCallback(
    (next: number, replace = false) =>
      updateListSearch({ page: next }, replace),
    [updateListSearch],
  )
  const { window: pageState, stale } = useServerPage({
    page,
    pageSize,
    total,
    isCurrent: coachesQuery.isSuccess && !coachesQuery.isPlaceholderData,
    onPageChange: setPage,
  })
  const hasFilter = searchTerm.trim().length > 0 || Boolean(gymFilter)

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
    await queryClient.invalidateQueries({ queryKey: ["superuser-athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["gyms"] })
    await queryClient.invalidateQueries({ queryKey: ["members"] })
    await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["athlete"] })
    await queryClient.invalidateQueries({ queryKey: ["coaches"] })
    await queryClient.invalidateQueries({
      queryKey: ["async-superuser-coaches"],
    })
    await queryClient.invalidateQueries({ queryKey: ["gym"] })
  }

  function openTransfer(row: SuperuserCoachRow) {
    setTransferTarget(row)
    setTransferGymId("")
    setTransferError(null)
  }

  async function saveTransfer() {
    if (!transferTarget) return
    setTransferError(null)
    if (!transferGymId) {
      setTransferError(t("superuser.destinationGymRequired"))
      return
    }
    setBusy(true)
    try {
      await SuperuserCoachesService.coachesTransferCoach({
        path: { membership_id: transferTarget.membership_id },
        body: { gym_id: transferGymId },
      })
      await invalidateAll()
      setTransferTarget(null)
      show(t("superuser.coachTransferred"), "success")
    } catch (err) {
      setTransferError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  function openEdit(row: SuperuserCoachRow) {
    setEditTarget(row)
    setEditForm({ full_name: row.full_name ?? "", phone: row.phone ?? "" })
    setEditError(null)
  }

  async function saveEdit() {
    if (!editTarget) return
    setEditError(null)
    if (!editForm.phone.trim()) {
      setEditError(t("validation.coachPhone"))
      return
    }
    setBusy(true)
    try {
      await SuperuserCoachesService.coachesUpdateCoach({
        path: { membership_id: editTarget.membership_id },
        body: {
          full_name: editForm.full_name.trim() || null,
          phone: editForm.phone.trim(),
        },
      })
      await invalidateAll()
      setEditTarget(null)
      show(t("superuser.coachUpdated"), "success")
    } catch (err) {
      setEditError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
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
              : "superuser.coachRemoved",
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
        <Button
          variant="text"
          size="sm"
          icon={<Eye size={14} />}
          onClick={() =>
            navigate({
              to: "/people/$userId",
              params: { userId: row.user_id },
              search: { gym: row.gym_id, kind: "COACH" },
            })
          }
        >
          {t("common.details")}
        </Button>
        <Button
          variant="text"
          size="sm"
          icon={<Pencil size={14} />}
          disabled={stale}
          onClick={() => openEdit(row)}
        >
          {t("common.edit")}
        </Button>
        {row.is_active ? (
          <Button
            variant="text"
            size="sm"
            icon={<ArrowRightLeft size={14} />}
            disabled={stale}
            onClick={() => openTransfer(row)}
          >
            {t("superuser.transferGym")}
          </Button>
        ) : null}
        {row.can_archive ? (
          <Button
            variant="text"
            size="sm"
            icon={
              row.is_active ? <Archive size={14} /> : <RotateCcw size={14} />
            }
            disabled={stale}
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
          icon={<UserMinus size={14} />}
          disabled={stale}
          onClick={() => setAction({ kind: "delete", row })}
        >
          {t("superuser.removeCoach")}
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
        search={searchTerm}
        onSearch={(value) => updateListSearch({ q: value, page: 1 }, true)}
        searchLabel={t("athletes.search")}
        clearSearchLabel={t("athletes.clearSearch")}
        countLabel={t("superuser.coachCountLabel", {
          count: formatNumber(total),
        })}
        view={view}
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
      ) : total === 0 ? (
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
                {t("superuser.addCoach")}
              </Button>
            )
          }
        />
      ) : view === "grid" ? (
        <div
          className={`m3-card-grid ${stale ? "is-updating" : ""}`}
          aria-busy={stale}
        >
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
          <div
            className={`m3-table-wrap m3-data-table-wrap ${
              stale ? "is-updating" : ""
            }`}
            aria-busy={stale}
          >
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

      {total > 0 ? (
        <PaginationBar
          page={pageState.page}
          pageCount={pageState.pageCount}
          pageSize={pageSize}
          total={pageState.total}
          start={pageState.start}
          end={pageState.end}
          loading={stale || coachesQuery.isFetching}
          onPageChange={setPage}
          onPageSizeChange={(size) =>
            updateListSearch({ size: size as PageSize, page: 1 })
          }
        />
      ) : null}

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

      <Dialog
        open={Boolean(editTarget)}
        title={t("superuser.editCoach")}
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
            <Button onClick={saveEdit} loading={busy}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <div className="m3-inline-alert m3-inline-alert--info">
            {t("superuser.sharedIdentityEditHint")}
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
        title={t("superuser.transferCoach")}
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
              disabled={!transferGymId}
            >
              {t("superuser.transferAction")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <div className="m3-inline-alert m3-inline-alert--info">
            {t("superuser.transferCoachHint")}
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
            onChange={setTransferGymId}
            options={gymOptions.filter(
              (option) => option.value !== transferTarget?.gym_id,
            )}
            required
          />
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
            ? "superuser.removeCoach"
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
