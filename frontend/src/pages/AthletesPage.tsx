import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import {
  Archive,
  ArrowLeft,
  ArrowRight,
  Copy,
  Eye,
  LayoutGrid,
  ListChecks,
  Mail,
  Phone,
  Plus,
  Search,
  Table2,
  Upload,
  UserRound,
  Users,
  X,
} from "lucide-react"
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type AthleteCreated,
  type AthleteSummary,
  AthletesService,
  type CoachPublic,
  GymsService,
} from "@/client"
import { AsyncPickerField } from "@/components/AsyncPickerField"
import { AthleteImportDialog } from "@/components/AthleteImportDialog"
import { AthleteListTabs } from "@/components/AthleteListTabs"
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
import { type RowActionItem, RowActionMenu } from "@/components/RowActionMenu"
import { useI18n } from "@/i18n"
import type { ListSearch, PageSize } from "@/lib/list-search"
import { useServerPage } from "@/lib/server-page"
import { useAsyncPicker } from "@/lib/use-async-picker"
import { useSnackbar } from "@/snackbar"

export function AthletesPage() {
  const { t, formatNumber, direction } = useI18n()
  const { activeGym, activeGymId, activeRole, isAdmin, me } = useAuth()
  const navigate = useNavigate({ from: "/gyms/$gymId/athletes/" })
  const searchParams = useSearch({ from: "/_app/gyms/$gymId/athletes/" })
  const page = searchParams.page ?? 1
  const pageSize = searchParams.size ?? 10
  const searchTerm = searchParams.q ?? ""
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const deferredSearch = useDeferredValue(searchTerm)
  const [view, setView] = useState<"grid" | "table">(() => {
    try {
      return localStorage.getItem("gym.athletes.view") === "table"
        ? "table"
        : "grid"
    } catch {
      return "grid"
    }
  })
  const [selected, setSelected] = useState<Record<string, AthleteSummary>>({})
  const selectAllRef = useRef<HTMLInputElement>(null)
  const tableWrapRef = useRef<HTMLDivElement>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [archiveTargets, setArchiveTargets] = useState<AthleteSummary[]>([])
  const [archiveBusy, setArchiveBusy] = useState(false)
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
  const scope = `${activeGymId ?? ""}|${activeRole ?? ""}|${deferredSearch}`

  const updateListSearch = useCallback(
    (patch: Partial<ListSearch>, replace = false) => {
      void navigate({
        to: ".",
        search: { ...searchParams, ...patch },
        replace,
      })
    },
    [navigate, searchParams],
  )

  const athletesQuery = useQuery({
    queryKey: ["athletes", scope, page, pageSize],
    queryFn: async () =>
      (
        await AthletesService.listAthletes({
          query: {
            q: deferredSearch,
            is_archived: false,
            offset: (page - 1) * pageSize,
            limit: pageSize,
          },
        })
      ).data,
    enabled: Boolean(activeGymId),
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[1] === scope ? previousData : undefined,
  })

  const coachPicker = useAsyncPicker<CoachPublic>({
    queryKey: ["async-gym-coaches", activeGymId],
    enabled: Boolean(addOpen && activeGymId && isAdmin),
    resetKey: activeGymId ?? "",
    fetchPage: async (search, offset, limit) =>
      (
        await GymsService.listCoaches({
          path: { gym_id: activeGymId! },
          query: { q: search, offset, limit },
        })
      ).data,
  })

  const athletes = athletesQuery.data?.data ?? []
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

  const selectedAthletes = Object.values(selected)
  const selectedOnPage = athletes.filter((athlete) =>
    Boolean(selected[athlete.user_id]),
  )
  const allSelected =
    athletes.length > 0 && selectedOnPage.length === athletes.length
  const someSelected = selectedOnPage.length > 0 && !allSelected
  const ForwardIcon = direction === "rtl" ? ArrowLeft : ArrowRight
  const hasSearch = searchTerm.trim().length > 0

  useEffect(() => {
    try {
      localStorage.setItem("gym.athletes.view", view)
    } catch {
      // Storage may be unavailable in private mode; the in-memory view still works.
    }
  }, [view])

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected
    }
  }, [someSelected])

  // biome-ignore lint/correctness/useExhaustiveDependencies: clear selection when the list scope changes
  useEffect(() => {
    setSelected({})
  }, [scope])

  useLayoutEffect(() => {
    if (view !== "table") return
    const wrapper = tableWrapRef.current
    if (wrapper) wrapper.scrollLeft = wrapper.scrollWidth
  }, [view])

  function toggleSelected(athlete: AthleteSummary) {
    setSelected((previous) => {
      const next = { ...previous }
      if (next[athlete.user_id]) delete next[athlete.user_id]
      else next[athlete.user_id] = athlete
      return next
    })
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelected((previous) => {
        const next = { ...previous }
        for (const athlete of athletes) delete next[athlete.user_id]
        return next
      })
      return
    }
    setSelected((previous) => {
      const next = { ...previous }
      for (const athlete of athletes) next[athlete.user_id] = athlete
      return next
    })
  }

  function clearSelection() {
    setSelected({})
  }

  async function archiveAthletes() {
    if (!archiveTargets.length || archiveBusy) return
    setArchiveBusy(true)
    const results = await Promise.allSettled(
      archiveTargets.map((athlete) =>
        AthletesService.archiveAthlete({
          path: { athlete_user_id: athlete.user_id },
        }),
      ),
    )
    const archived = results.filter(
      (result) => result.status === "fulfilled",
    ).length
    const failed = results.length - archived
    await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["athlete"] })
    if (failed === 0 && archived === 1) {
      show(t("athletes.archived"), "success")
    } else {
      show(
        t("athletes.archiveSummary", {
          count: formatNumber(archived),
          failed: formatNumber(failed),
        }),
        failed ? "error" : "success",
      )
    }
    setArchiveTargets([])
    setSelected({})
    setArchiveBusy(false)
  }

  function openAthlete(userId: string) {
    navigate({
      to: "/gyms/$gymId/athletes/$athleteId",
      params: { gymId: activeGymId!, athleteId: userId },
    })
  }

  function openOverview(userId: string) {
    navigate({
      to: "/people/$userId",
      params: { userId },
      search: { gym: activeGymId!, kind: "ATHLETE" },
    })
  }

  function tableActions(athlete: AthleteSummary) {
    const items: RowActionItem[] = [
      {
        key: "open",
        label: t("common.open"),
        icon: <ForwardIcon size={15} />,
        onSelect: () => openAthlete(athlete.user_id),
      },
    ]
    if (isAdmin) {
      items.push({
        key: "archive",
        label: t("athletes.archive"),
        icon: <Archive size={15} />,
        onSelect: () => setArchiveTargets([athlete]),
      })
    }
    return (
      <div className="m3-row-actions">
        {isAdmin ? (
          <Button
            variant="text"
            size="sm"
            icon={<Eye size={15} />}
            onClick={() => openOverview(athlete.user_id)}
          >
            {t("common.details")}
          </Button>
        ) : null}
        <RowActionMenu
          items={items}
          label={t("common.moreActions")}
          disabled={stale}
        />
      </div>
    )
  }

  if (!activeGym) {
    return (
      <PageHeader
        title={t("athletes.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

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
          <>
            {isAdmin ? (
              <Button
                variant="outlined"
                icon={<Upload size={16} />}
                onClick={() => setImportOpen(true)}
              >
                {t("athletes.bulkImport")}
              </Button>
            ) : null}
            {canCreate ? (
              <Button
                icon={<Plus size={17} />}
                onClick={() => setAddOpen(true)}
              >
                {t("athletes.add")}
              </Button>
            ) : null}
          </>
        }
      />

      {isAdmin ? <AthleteListTabs active="active" /> : null}

      <section className="m3-list-toolbar">
        <div className="m3-list-toolbar__search">
          <TextField
            label={t("athletes.search")}
            type="search"
            name="search"
            value={searchTerm}
            onChange={(event) =>
              updateListSearch({ q: event.target.value, page: 1 }, true)
            }
            leading={<Search size={18} aria-hidden />}
            trailing={
              searchTerm ? (
                <button
                  type="button"
                  className="m3-search-clear"
                  aria-label={t("athletes.clearSearch")}
                  onClick={() => updateListSearch({ q: "", page: 1 }, true)}
                >
                  <X size={15} aria-hidden />
                </button>
              ) : undefined
            }
          />
        </div>
        <div className="m3-list-toolbar__actions">
          <span className="m3-count-chip" aria-live="polite">
            {t("athletes.countLabel", {
              count: formatNumber(total),
            })}
          </span>
          <fieldset className="m3-view-toggle">
            <legend className="sr-only">{t("athletes.view")}</legend>
            <button
              type="button"
              className={`m3-view-toggle__option ${
                view === "grid" ? "is-active" : ""
              }`}
              aria-pressed={view === "grid"}
              aria-label={t("athletes.gridView")}
              title={t("athletes.gridView")}
              onClick={() => setView("grid")}
            >
              <LayoutGrid size={16} aria-hidden />
              <span>{t("athletes.gridView")}</span>
            </button>
            <button
              type="button"
              className={`m3-view-toggle__option ${
                view === "table" ? "is-active" : ""
              }`}
              aria-pressed={view === "table"}
              aria-label={t("athletes.tableView")}
              title={t("athletes.tableView")}
              onClick={() => setView("table")}
            >
              <Table2 size={16} aria-hidden />
              <span>{t("athletes.tableView")}</span>
            </button>
          </fieldset>
        </div>
      </section>

      {athletesQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : athletesQuery.isError ? (
        <ErrorState
          message={translateApiError(athletesQuery.error, t)}
          onRetry={() => athletesQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : total === 0 ? (
        <EmptyState
          icon={hasSearch ? <Search size={26} /> : <Users size={26} />}
          title={hasSearch ? t("common.noResults") : t("athletes.empty")}
          description={
            hasSearch ? t("athletes.noResultsHint") : t("athletes.emptyHint")
          }
          action={
            hasSearch ? (
              <Button
                variant="outlined"
                icon={<X size={16} />}
                onClick={() => updateListSearch({ q: "", page: 1 }, true)}
              >
                {t("athletes.clearSearch")}
              </Button>
            ) : canCreate ? (
              <Button
                icon={<Plus size={17} />}
                onClick={() => setAddOpen(true)}
              >
                {t("athletes.add")}
              </Button>
            ) : undefined
          }
        />
      ) : view === "grid" ? (
        <div
          className={`m3-card-grid ${stale ? "is-updating" : ""}`}
          aria-busy={stale}
        >
          {athletes.map((athlete) => (
            <div
              key={athlete.user_id}
              className={`m3-entity-card ${
                athlete.is_archived ? "is-archived" : ""
              }`}
            >
              <button
                type="button"
                className="m3-entity-card__stretch"
                aria-label={`${t("common.open")} ${
                  athlete.full_name ?? athlete.email
                }`}
                onClick={() => openAthlete(athlete.user_id)}
              />
              <div className="m3-entity-card__body">
                <div className="m3-entity-card__head">
                  <div className="m3-entity-card__identity">
                    <Avatar name={athlete.full_name ?? athlete.email} />
                    <div className="m3-entity-card__person">
                      <div
                        className="m3-entity-card__title"
                        title={athlete.full_name ?? athlete.email}
                      >
                        {athlete.full_name ?? athlete.email}
                      </div>
                      <div
                        className="m3-entity-card__email truncate"
                        dir="ltr"
                        title={athlete.email}
                      >
                        {athlete.email}
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
                    <UserRound size={13} aria-hidden />{" "}
                    {athlete.coach_name ?? t("athletes.noCoach")}
                  </span>
                  {athlete.phone ? (
                    <span dir="ltr">
                      <Phone size={13} aria-hidden /> {athlete.phone}
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="m3-entity-card__footer">
                {athlete.active_program_title ? (
                  <span className="m3-status m3-status--active">
                    {athlete.active_program_title}
                    {athlete.active_program_version
                      ? ` · ${t("program.versionLabel", {
                          version: formatNumber(athlete.active_program_version),
                        })}`
                      : ""}
                  </span>
                ) : (
                  <span className="m3-status m3-status--archived">
                    {t("athletes.noActiveProgram")}
                  </span>
                )}
                <div className="m3-entity-card__actions">
                  {isAdmin ? (
                    <Button
                      variant="text"
                      size="sm"
                      icon={<Eye size={14} />}
                      onClick={() => openOverview(athlete.user_id)}
                    >
                      {t("common.details")}
                    </Button>
                  ) : null}
                  {isAdmin ? (
                    <Button
                      variant="text"
                      size="sm"
                      icon={<Archive size={14} />}
                      disabled={stale}
                      onClick={() => setArchiveTargets([athlete])}
                    >
                      {t("athletes.archive")}
                    </Button>
                  ) : null}
                  <button
                    type="button"
                    className="m3-entity-card__open"
                    onClick={() => openAthlete(athlete.user_id)}
                  >
                    {t("common.open")}
                    <ForwardIcon size={14} aria-hidden />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <>
          {selectedAthletes.length > 0 ? (
            <div className="m3-selection-bar" role="status" aria-live="polite">
              <span className="m3-selection-bar__count">
                <ListChecks size={16} aria-hidden />
                {t("athletes.selectedCount", {
                  count: formatNumber(selectedAthletes.length),
                })}
              </span>
              <div className="row" style={{ gap: 4 }}>
                {isAdmin ? (
                  <Button
                    variant="text"
                    size="sm"
                    icon={<Archive size={15} />}
                    disabled={stale}
                    onClick={() => setArchiveTargets(selectedAthletes)}
                  >
                    {t("athletes.archiveSelected")}
                  </Button>
                ) : null}
                <Button variant="text" size="sm" onClick={clearSelection}>
                  {t("athletes.clearSelection")}
                </Button>
              </div>
            </div>
          ) : null}
          <Card className="m3-data-card">
            <div
              ref={tableWrapRef}
              className={`m3-table-wrap m3-data-table-wrap ${
                stale ? "is-updating" : ""
              }`}
              aria-busy={stale}
            >
              <table className="m3-table m3-data-table m3-people-table m3-people-table--athletes">
                <thead>
                  <tr>
                    <th scope="col" className="m3-data-table__check">
                      <label className="m3-checkbox">
                        <input
                          ref={selectAllRef}
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleSelectAll}
                          disabled={stale}
                          aria-label={t("athletes.selectPage")}
                        />
                      </label>
                    </th>
                    <th scope="col" className="m3-people-table__person">
                      {t("athletes.athlete")}
                    </th>
                    <th scope="col" className="m3-people-table__coach">
                      {t("athletes.coach")}
                    </th>
                    <th scope="col" className="m3-people-table__phone">
                      {t("athletes.phone")}
                    </th>
                    <th scope="col" className="m3-people-table__status">
                      {t("athletes.status")}
                    </th>
                    <th scope="col" className="m3-people-table__program">
                      {t("athletes.activeProgram")}
                    </th>
                    <th scope="col" className="m3-people-table__actions">
                      {t("common.actions")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {athletes.map((athlete) => (
                    <tr
                      key={athlete.user_id}
                      className={selected[athlete.user_id] ? "is-selected" : ""}
                    >
                      <td className="m3-data-table__check">
                        <label className="m3-checkbox">
                          <input
                            type="checkbox"
                            checked={Boolean(selected[athlete.user_id])}
                            onChange={() => toggleSelected(athlete)}
                            disabled={stale}
                            aria-label={`${t("athletes.select")} ${
                              athlete.full_name ?? athlete.email
                            }`}
                          />
                        </label>
                      </td>
                      <td className="m3-people-table__person">
                        <button
                          type="button"
                          className="m3-data-table__identity"
                          onClick={() => openAthlete(athlete.user_id)}
                        >
                          <Avatar name={athlete.full_name ?? athlete.email} />
                          <span className="m3-data-table__person">
                            <strong title={athlete.full_name ?? athlete.email}>
                              {athlete.full_name ?? athlete.email}
                            </strong>
                            <span
                              className="m3-data-table__email truncate"
                              dir="ltr"
                              title={athlete.email}
                            >
                              {athlete.email}
                            </span>
                          </span>
                        </button>
                      </td>
                      <td className="m3-people-table__coach">
                        <span
                          title={athlete.coach_name ?? t("athletes.noCoach")}
                        >
                          {athlete.coach_name ?? t("athletes.noCoach")}
                        </span>
                      </td>
                      <td dir="ltr" className="m3-people-table__phone">
                        {athlete.phone ?? "—"}
                      </td>
                      <td className="m3-people-table__status">
                        {athlete.is_archived ? (
                          <StatusBadge status="archived" />
                        ) : (
                          <StatusBadge
                            status={athlete.is_active ? "active" : "inactive"}
                          />
                        )}
                      </td>
                      <td className="m3-people-table__program">
                        {athlete.active_program_title ? (
                          <span
                            className="m3-status m3-status--active"
                            title={athlete.active_program_title}
                          >
                            {athlete.active_program_title}
                            {athlete.active_program_version
                              ? ` · ${formatNumber(
                                  athlete.active_program_version,
                                )}`
                              : ""}
                          </span>
                        ) : (
                          <span className="muted">
                            {t("athletes.noActiveProgram")}
                          </span>
                        )}
                      </td>
                      <td className="m3-people-table__actions">
                        {tableActions(athlete)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
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

      <ConfirmDialog
        open={archiveTargets.length > 0}
        title={
          archiveTargets.length === 1
            ? t("athletes.archiveTitle")
            : t("athletes.archiveTitleMultiple", {
                count: formatNumber(archiveTargets.length),
              })
        }
        description={t("athletes.archiveWarning")}
        confirmLabel={t("athletes.confirmArchive")}
        cancelLabel={t("common.cancel")}
        onConfirm={archiveAthletes}
        onClose={() => setArchiveTargets([])}
        destructive
        loading={archiveBusy}
      />

      <AthleteImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={() => {
          void queryClient.invalidateQueries({
            queryKey: ["athletes", activeGymId],
          })
          void queryClient.invalidateQueries({ queryKey: ["gyms"] })
        }}
        gymId={activeGymId!}
      />

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
              <AsyncPickerField
                label={t("athletes.coach")}
                value={form.coach_user_id}
                onChange={(value) => setForm({ ...form, coach_user_id: value })}
                picker={coachPicker}
                getOption={(coach) => ({
                  value: coach.user_id,
                  label: coach.full_name ?? coach.email,
                })}
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
