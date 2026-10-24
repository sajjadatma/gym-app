import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { RotateCcw, Search, Trash2, Users, X } from "lucide-react"
import { useDeferredValue, useEffect, useRef, useState } from "react"
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
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function ArchivedAthletesPage() {
  const { t, formatNumber } = useI18n()
  const { activeGym, activeGymId, activeRole, isAdmin, me } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [deleteTargets, setDeleteTargets] = useState<DeleteAthleteTarget[]>([])
  const [busy, setBusy] = useState(false)
  const selectAllRef = useRef<HTMLInputElement>(null)

  const archivedQuery = useQuery({
    queryKey: ["athletes", activeGymId, "archived", deferredSearch],
    queryFn: async () =>
      (
        await AthletesService.listAthletes({
          query: { q: deferredSearch, include_archived: true },
        })
      ).data,
    enabled: Boolean(activeGymId && isAdmin),
    staleTime: 0,
    refetchOnWindowFocus: true,
  })

  useEffect(() => {
    setSelected(new Set())
  }, [])

  const archived = (archivedQuery.data?.data ?? []).filter((athlete) => {
    if (!athlete.is_archived) return false
    if (activeRole === "COACH" && !isAdmin)
      return athlete.coach_user_id === me?.id
    return true
  })

  const selectedAthletes = archived.filter((athlete) =>
    selected.has(athlete.user_id),
  )
  const allSelected =
    archived.length > 0 && selectedAthletes.length === archived.length
  const someSelected = selectedAthletes.length > 0 && !allSelected

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someSelected
    }
  }, [someSelected])

  function toggleSelected(userId: string) {
    setSelected((previous) => {
      const next = new Set(previous)
      if (next.has(userId)) next.delete(userId)
      else next.add(userId)
      return next
    })
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelected(new Set())
      return
    }
    setSelected(new Set(archived.map((athlete) => athlete.user_id)))
  }

  function openAthlete(userId: string) {
    navigate({
      to: "/athletes/$athleteId",
      params: { athleteId: userId },
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
    setSelected(new Set())
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
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            leading={<Search size={18} aria-hidden />}
            trailing={
              search ? (
                <button
                  type="button"
                  className="m3-search-clear"
                  aria-label={t("athletes.clearSearch")}
                  onClick={() => setSearch("")}
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
              count: formatNumber(archived.length),
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
      ) : archived.length === 0 ? (
        <EmptyState
          icon={<Users size={26} />}
          title={t("athletes.archivedEmpty")}
          description={t("athletes.archivedEmptyHint")}
          action={
            <Button
              variant="outlined"
              icon={<RotateCcw size={16} />}
              onClick={() => navigate({ to: "/athletes" })}
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
                  onClick={() => void restoreAthletes(selectedAthletes)}
                >
                  {t("athletes.restoreSelected")}
                </Button>
                <Button
                  variant="text"
                  size="sm"
                  icon={<Trash2 size={15} />}
                  className="m3-text-danger"
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
            <div className="m3-table-wrap">
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
                          aria-label={t("athletes.selectAll")}
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
                      className={
                        selected.has(athlete.user_id) ? "is-selected" : ""
                      }
                    >
                      <td className="m3-data-table__check">
                        <label className="m3-checkbox">
                          <input
                            type="checkbox"
                            checked={selected.has(athlete.user_id)}
                            onChange={() => toggleSelected(athlete.user_id)}
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
                            icon={<RotateCcw size={15} />}
                            aria-label={t("athletes.restore")}
                            onClick={() => void restoreAthletes([athlete])}
                            disabled={busy}
                          >
                            {t("athletes.restore")}
                          </Button>
                          <Button
                            variant="text"
                            size="sm"
                            icon={<Trash2 size={15} />}
                            aria-label={t("athletes.delete")}
                            className="m3-text-danger"
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

      <DeleteAthletesDialog
        open={deleteTargets.length > 0}
        athletes={deleteTargets}
        onClose={() => setDeleteTargets([])}
        onDeleted={() => {
          setDeleteTargets([])
          setSelected(new Set())
        }}
      />
    </>
  )
}
