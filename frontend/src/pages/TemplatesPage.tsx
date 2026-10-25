import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Bookmark, ClipboardList, Copy, Plus, UserRound } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  AthletesService,
  type ProgramTemplateSummary,
  TemplatesService,
} from "@/client"
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  SearchableSelectField,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { fetchAllPages } from "@/lib/fetch-all-pages"
import { useSnackbar } from "@/snackbar"

export function TemplatesPage() {
  const { t, formatDate, formatNumber } = useI18n()
  const { activeGym, activeGymId, activeRole, me } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [applyTemplate, setApplyTemplate] =
    useState<ProgramTemplateSummary | null>(null)
  const [athleteId, setAthleteId] = useState("")
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const templatesQuery = useQuery({
    queryKey: ["templates", activeGymId],
    queryFn: async () => (await TemplatesService.listTemplates()).data.data,
    enabled: Boolean(activeGymId),
  })

  const athletesQuery = useQuery({
    queryKey: ["athletes", activeGymId, "templates-apply", activeRole],
    queryFn: async () =>
      // The picker must offer every eligible athlete, not one page.
      fetchAllPages(async (offset, limit) => {
        const response = await AthletesService.listAthletes({
          query: { q: "", is_archived: false, offset, limit },
        })
        return response.data
      }),
    enabled: Boolean(activeGymId && applyTemplate),
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("templates.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  const canManage = activeRole === "GYM_ADMIN" || activeRole === "COACH"
  const templates = (templatesQuery.data ?? []).filter(
    (template) => activeRole !== "COACH" || template.created_by_id === me?.id,
  )
  const athletes = athletesQuery.data ?? []

  async function apply() {
    if (!applyTemplate || !athleteId) {
      setError(t("validation.selectAthlete"))
      return
    }
    setApplying(true)
    setError(null)
    try {
      const response = await TemplatesService.applyTemplate({
        path: { template_id: applyTemplate.id },
        body: { athlete_user_id: athleteId },
      })
      await queryClient.invalidateQueries({
        queryKey: ["programs", activeGymId],
      })
      setApplyTemplate(null)
      setAthleteId("")
      show(t("templates.applied"), "success")
      navigate({
        to: "/gyms/$gymId/programs/$versionId/edit",
        params: { gymId: activeGymId!, versionId: response.data.id },
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setApplying(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t("templates.title")}
        subtitle={`${activeGym.name} · ${t("templates.subtitle")}`}
        actions={
          canManage ? (
            <Button
              icon={<Plus size={17} />}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/templates/new",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("templates.create")}
            </Button>
          ) : undefined
        }
      />

      {templatesQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : templatesQuery.isError ? (
        <ErrorState
          message={translateApiError(templatesQuery.error, t)}
          onRetry={() => templatesQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : !templates.length ? (
        <EmptyState
          icon={<Bookmark size={26} />}
          title={t("templates.empty")}
          description={t("templates.emptyHint")}
          action={
            canManage ? (
              <Button
                icon={<Plus size={17} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/templates/new",
                    params: { gymId: activeGymId! },
                  })
                }
              >
                {t("templates.create")}
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="m3-card-grid">
          {templates.map((template) => (
            <Card key={template.id} className="m3-card--outlined">
              <div className="m3-entity-card__head">
                <div>
                  <div className="m3-entity-card__title">{template.name}</div>
                  <div className="m3-entity-card__meta">
                    <span>
                      <ClipboardList
                        size={13}
                        style={{ verticalAlign: "middle" }}
                      />{" "}
                      {t("templates.dayCount", {
                        count: formatNumber(template.day_count),
                      })}
                    </span>
                  </div>
                </div>
                <span className="m3-chip m3-chip--selected">
                  {t("templates.reusable")}
                </span>
              </div>
              {template.goal ? (
                <p className="muted" style={{ fontSize: 12 }}>
                  {template.goal}
                </p>
              ) : null}
              <div className="m3-entity-card__meta">
                <span>
                  <UserRound size={13} style={{ verticalAlign: "middle" }} />{" "}
                  {template.created_by_name ?? ""}
                </span>
                <span>{formatDate(template.updated_at)}</span>
              </div>
              <div className="m3-entity-card__footer">
                <Button
                  variant="text"
                  size="sm"
                  onClick={() =>
                    navigate({
                      to: "/gyms/$gymId/templates/$templateId/edit",
                      params: { gymId: activeGymId!, templateId: template.id },
                    })
                  }
                >
                  {t("common.edit")}
                </Button>
                <Button
                  variant="tonal"
                  size="sm"
                  icon={<Copy size={14} />}
                  onClick={() => {
                    setError(null)
                    setAthleteId("")
                    setApplyTemplate(template)
                  }}
                >
                  {t("templates.apply")}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog
        open={Boolean(applyTemplate)}
        title={t("templates.applyTitle")}
        description={t("templates.copyNote")}
        onClose={() => setApplyTemplate(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setApplyTemplate(null)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={apply} loading={applying} disabled={!athleteId}>
              {t("templates.apply")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <p className="muted">{applyTemplate?.name}</p>
          {athletesQuery.isLoading ? (
            <Spinner label={t("common.loading")} />
          ) : (
            <SearchableSelectField
              label={t("templates.selectAthlete")}
              value={athleteId}
              onChange={setAthleteId}
              options={athletes.map((athlete) => ({
                value: athlete.user_id,
                label: athlete.full_name ?? athlete.email,
              }))}
              placeholder={t("common.choose")}
              required
            />
          )}
        </div>
      </Dialog>
    </>
  )
}
