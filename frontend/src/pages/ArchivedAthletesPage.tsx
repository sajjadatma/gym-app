import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearch } from "@tanstack/react-router"
import { Eye, RotateCcw, Search, Trash2, Users, X } from "lucide-react"
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type AthleteSummary, AthletesService } from "@/client"
import { AthleteListTabs } from "@/components/AthleteListTabs"
import {
  DeleteAthletesDialog,
  type DeleteAthleteTarget,
} from "@/components/DeleteAthletesDialog"
import {
  Avatar,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
  TextField,
} from "@/components/M3"
import { PaginationBar } from "@/components/Pagination"
import { useI18n } from "@/i18n"
import type { ListSearch, PageSize } from "@/lib/list-search"
import { useServerPage } from "@/lib/server-page"
import { useSnackbar } from "@/snackbar"

export function ArchivedAthletesPage() {
  const { t, formatNumber } = useI18n()
  const { activeGym, activeGymId, isAdmin } = useAuth()
  const navigate = useNavigate({ from: "/gyms/$gymId/athletes/archived" })
  const searchParams = useSearch({
    from: "/_app/gyms/$gymId/athletes/archived",
  })
  const page = searchParams.page ?? 1
  const pageSize = searchParams.size ?? 10
  const searchTerm = searchParams.q ?? ""
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const deferredSearch = useDeferredValue(searchTerm)
  const [selected, setSelected] = useState<Record<string, AthleteSummary>>({})
  const [deleteTargets, setDeleteTargets] = useState<DeleteAthleteTarget[]>([])
  const [busy, setBusy] = useState(false)
  const selectAllRef = useRef<HTMLInputElement>(null)

  const scope = `${activeGymId ?? ""}|${deferredSearch}`

  const updateListSearch = useCallback(
    (patch: Partial<ListSearch>, replace = false) => {
      void navigate({
        search: (previous) => ({ ...previous, ...patch }),
        replace,
      })
    },
    [navigate],
  )

  const archivedQuery = useQuery({
    queryKey: ["athletes", "archived", scope, page, pageSize],
    queryFn: async () =>
      (
        await AthletesService.listAthletes({
          query: {
            q: deferredSearch,
            is_archived: true,
            offset: (page - 1) * pageSize,
            limit: pageSize,
          },
        })
      ).data,
    enabled: Boolean(activeGymId && isAdmin),
    staleTime: 0,
    refetchOnWindowFocus: true,
    placeholderData: (previousData, previousQuery) =>
      previousQuery?.queryKey[2] === scope ? previousData : undefined,
  })

  const archived = archivedQuery.data?.data ?? []
  const total = archivedQuery.data?.count ?? 0
  const setPage = useCallback(
    (next: number, replace = false) =>
      updateListSearch({ page: next }, replace),
    [updateListSearch],
  )
  const { window: pageState, stale } = useServerPage({
    page,
    pageSize,
    total,
    isCurrent: archivedQuery.isSuccess && !archivedQuery.isPlaceholderData,
    onPageChange: setPage,
  })

  // biome-ignore lint/correctness/useExhaustiveDependencies: clear selection when the list scope changes
  useEffect(() => {
    setSelected({})
  }, [scope])

  const selectedAthletes = Object.values(selected)
  const selectedOnPage = archived.filter((athlete) =>
    Boolean(selected[athlete.user_id]),
  )
  const allSelected =
    archived.length > 0 && selectedOnPage.length === archived.length
  const someSelected = selectedOnPage.length > 0 && !allSelected

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected
    }
  }, [someSelected])

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
        for (const athlete of archived) delete next[athlete.user_id]
        return next
      })
      return
    }
    setSelected((previous) => {
      const next = { ...previous }
      for (const athlete of archived) next[athlete.user_id] = athlete
      return next
    })
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

  async function restoreAthletes(athletesToRestore: AthleteSummary[]) {
    if (!athletesToRestore.length || busy) return
    setBusy(true)
    const results = await Promise.allSettled(
      athletesToRestore.map((athlete) =>
        AthletesService.restoreAthlete({
          path: { athlete_user_id: athlete.user_id },
        }),
      ),
    )
    const restored = results.filter(
      (result) => result.status === "fulfilled",
    ).length
    const failed = results.length - restored
    await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["athlete"] })
    if (failed === 0 && restored === 1) {
      show(t("athletes.restored"), "success")
    } else {
      show(
        t("athletes.restoreSummary", {
          restored: formatNumber(restored),
          failed: formatNumber(failed),
        }),
        failed ? "error" : "success",
      )
    }
    setSelected({})
    setBusy(false)
  }

  function toDeleteTarget(athlete: AthleteSummary): DeleteAthleteTarget {
    return {
      user_id: athlete.user_id,
      email: athlete.email,
      full_name: athlete.full_name,
    }
  }

  if (!activeGym) {
    return (
      <PageHeader
        title={t("athletes.archivedTitle")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  if (!isAdmin) {
    return (
      <>
        <PageHeader
          title={t("athletes.archivedTitle")}
          subtitle={t("athletes.archivedSubtitle")}
        />
        <ErrorState message={t("errors.gym_admin_required")} />
      </>
    )
  }

  return (
    <>
      <PageHeader
        title={t("athletes.archivedTitle")}
        subtitle={`${activeGym.name} · ${t("athletes.archivedSubtitle")}`}
      />
      <AthleteListTabs active="archived" />

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
        </div>
      </section>

      {archivedQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : archivedQuery.isError ? (
        <ErrorState
          message={translateApiError(archivedQuery.error, t)}
          onRetry={() => archivedQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : total === 0 ? (
        <EmptyState
          icon={<Users size={26} />}
          title={t("athletes.archivedEmpty")}
          description={t("athletes.archivedEmptyHint")}
          action={
            <Button
              variant="outlined"
              icon={<RotateCcw size={16} />}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/athletes",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("athletes.backToActive")}
            </Button>
          }
        />
      ) : (
        <>
          {selectedAthletes.length > 0 ? (
            <div className="m3-selection-bar" role="status" aria-live="polite">
              <span className="m3-selection-bar__count">
                {t("athletes.selectedCount", {
                  count: formatNumber(selectedAthletes.length),
                })}
              </span>
              <div className="row" style={{ gap: 4 }}>
                <Button
                  variant="text"
                  size="sm"
                  icon={<RotateCcw size={15} />}
                  loading={busy}
                  disabled={stale}
                  onClick={() => void restoreAthletes(selectedAthletes)}
                >
                  {t("athletes.restoreSelected")}
                </Button>
                <Button
                  variant="text"
                  size="sm"
                  icon={<Trash2 size={15} />}
                  className="m3-text-danger"
                  disabled={stale}
                  onClick={() =>
                    setDeleteTargets(selectedAthletes.map(toDeleteTarget))
                  }
                >
                  {t("athletes.deleteSelected")}
                </Button>
              </div>
            </div>
          ) : null}

          <Card className="m3-data-card">
            <div
              className={`m3-table-wrap ${stale ? "is-updating" : ""}`}
              aria-busy={stale}
            >
              <table className="m3-table m3-data-table m3-archive-table">
                <thead>
                  <tr>
                    <th scope="col" className="m3-data-table__check">
                      <label className="m3-checkbox">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          ref={selectAllRef}
                          onChange={toggleSelectAll}
                          disabled={stale}
                          aria-label={t("athletes.selectPage")}
                        />
                      </label>
                    </th>
                    <th scope="col">{t("athletes.athlete")}</th>
                    <th scope="col" className="m3-data-table__coach">
                      {t("athletes.coach")}
                    </th>
                    <th scope="col" className="m3-data-table__phone">
                      {t("athletes.phone")}
                    </th>
                    <th scope="col" className="m3-archive-table__actions">
                      <span className="sr-only">{t("common.actions")}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {archived.map((athlete) => (
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
                      <td>
                        <button
                          type="button"
                          className="m3-data-table__identity"
                          onClick={() => openAthlete(athlete.user_id)}
                        >
                          <Avatar name={athlete.full_name ?? athlete.email} />
                          <span className="m3-data-table__person">
                            <strong className="truncate">
                              {athlete.full_name ?? athlete.email}
                            </strong>
                            <span
                              className="m3-data-table__email truncate"
                              dir="ltr"
                            >
                              {athlete.email}
                            </span>
                          </span>
                        </button>
                      </td>
                      <td className="m3-data-table__coach">
                        {athlete.coach_name ?? t("athletes.noCoach")}
                      </td>
                      <td dir="ltr" className="m3-data-table__phone">
                        {athlete.phone ?? "—"}
                      </td>
                      <td className="m3-archive-table__actions">
                        <div className="row" style={{ gap: 2 }}>
                          <Button
                            variant="text"
                            size="sm"
                            icon={<Eye size={15} />}
                            onClick={() => openOverview(athlete.user_id)}
                          >
                            {t("common.details")}
                          </Button>
                          <Button
                            variant="text"
                            size="sm"
                            icon={<RotateCcw size={15} />}
                            aria-label={t("athletes.restore")}
                            onClick={() => void restoreAthletes([athlete])}
                            disabled={busy || stale}
                          >
                            {t("athletes.restore")}
                          </Button>
                          <Button
                            variant="text"
                            size="sm"
                            icon={<Trash2 size={15} />}
                            aria-label={t("athletes.delete")}
                            className="m3-text-danger"
                            disabled={stale}
                            onClick={() =>
                              setDeleteTargets([toDeleteTarget(athlete)])
                            }
                          >
                            {t("athletes.delete")}
                          </Button>
                        </div>
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
          loading={stale || archivedQuery.isFetching}
          onPageChange={setPage}
          onPageSizeChange={(size) =>
            updateListSearch({ size: size as PageSize, page: 1 })
          }
        />
      ) : null}

      <DeleteAthletesDialog
        open={deleteTargets.length > 0}
        athletes={deleteTargets}
        onClose={() => setDeleteTargets([])}
        onDeleted={() => {
          setDeleteTargets([])
          setSelected({})
        }}
      />
    </>
  )
}
