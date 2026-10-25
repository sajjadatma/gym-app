import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useBlocker, useNavigate } from "@tanstack/react-router"
import { Bookmark, Save } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type DayInput, ExercisesService, TemplatesService } from "@/client"
import {
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  PageHeader,
  Spinner,
  TextField,
} from "@/components/M3"
import { ProgramStructureEditor } from "@/components/ProgramStructureEditor"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function TemplateEditorPage({ templateId }: { templateId?: string }) {
  const { t } = useI18n()
  const { activeGym, activeGymId, activeRole } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [meta, setMeta] = useState({
    name: "",
    goal: "",
    notes: "",
  })
  const [days, setDays] = useState<DayInput[]>([])
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const templateQuery = useQuery({
    queryKey: ["template", activeGymId, templateId],
    queryFn: async () =>
      (
        await TemplatesService.readTemplate({
          path: { template_id: templateId! },
        })
      ).data,
    enabled: Boolean(activeGymId && templateId),
  })

  const exercisesQuery = useQuery({
    queryKey: ["exercises", activeGymId, "template-builder"],
    queryFn: async () =>
      (await ExercisesService.listExercises({ query: { q: "" } })).data.data,
    enabled: Boolean(activeGymId),
  })

  const template = templateQuery.data
  useEffect(() => {
    if (!template) return
    setMeta({
      name: template.name,
      goal: template.goal ?? "",
      notes: template.notes ?? "",
    })
    setDays(template.days as DayInput[])
    setDirty(false)
  }, [template])

  const shouldBlock = useMemo(() => dirty, [dirty])
  const blocker = useBlocker({
    shouldBlockFn: () => shouldBlock,
    withResolver: true,
    disabled: !shouldBlock,
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("templates.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }
  if (activeRole !== "GYM_ADMIN" && activeRole !== "COACH") {
    return <ErrorState message={t("errors.gym_staff_required")} />
  }
  if (templateId && templateQuery.isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (templateId && (templateQuery.isError || !template)) {
    return (
      <ErrorState
        message={translateApiError(templateQuery.error, t)}
        onRetry={() => templateQuery.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  async function save() {
    if (!meta.name.trim()) {
      setError(t("validation.title"))
      return
    }
    setSaving(true)
    setError(null)
    try {
      const body = {
        name: meta.name.trim(),
        goal: meta.goal || null,
        notes: meta.notes || null,
        days,
      }
      if (templateId) {
        const response = await TemplatesService.updateTemplate({
          path: { template_id: templateId },
          body,
        })
        queryClient.setQueryData(
          ["template", activeGymId, templateId],
          response.data,
        )
        show(t("templates.updated"), "success")
      } else {
        const response = await TemplatesService.createTemplate({ body })
        await queryClient.invalidateQueries({
          queryKey: ["templates", activeGymId],
        })
        show(t("templates.created"), "success")
        setDirty(false)
        navigate({
          to: "/gyms/$gymId/templates/$templateId/edit",
          params: { gymId: activeGymId!, templateId: response.data.id },
        })
        return
      }
      await queryClient.invalidateQueries({
        queryKey: ["templates", activeGymId],
      })
      setDirty(false)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={templateId ? t("templates.editTitle") : t("templates.newTitle")}
        subtitle={`${activeGym.name} · ${t("templates.subtitle")}`}
        onBack={() =>
          navigate({
            to: "/gyms/$gymId/templates",
            params: { gymId: activeGymId! },
          })
        }
        backLabel={t("common.back")}
        actions={
          <Button icon={<Save size={16} />} onClick={save} loading={saving}>
            {t("templates.save")}
          </Button>
        }
      />

      <div className="m3-banner">
        <Bookmark size={18} />
        <span>{t("templates.copyNote")}</span>
      </div>

      {error ? (
        <div className="m3-inline-alert" style={{ marginBottom: 14 }}>
          {error}
        </div>
      ) : null}

      <div className="m3-builder-layout">
        <div className="m3-builder-meta">
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("templates.name")}</h2>
                <p className="m3-section__subtitle">
                  {t("templates.reusable")}
                </p>
              </div>
            </div>
            <div className="stack">
              <TextField
                label={t("templates.name")}
                value={meta.name}
                onChange={(event) => {
                  setMeta({ ...meta, name: event.target.value })
                  setDirty(true)
                }}
                required
              />
              <TextField
                label={t("program.goal")}
                value={meta.goal}
                onChange={(event) => {
                  setMeta({ ...meta, goal: event.target.value })
                  setDirty(true)
                }}
              />
              <TextField
                label={t("program.notes")}
                value={meta.notes}
                onChange={(event) => {
                  setMeta({ ...meta, notes: event.target.value })
                  setDirty(true)
                }}
                multiline
                rows={4}
              />
            </div>
          </Card>
        </div>

        <div>
          <div className="row row--between" style={{ marginBottom: 12 }}>
            <div>
              <h2>{t("program.days")}</h2>
              <p className="muted" style={{ fontSize: 12 }}>
                {dirty ? t("program.dirty") : t("templates.reusable")}
              </p>
            </div>
          </div>
          <ProgramStructureEditor
            days={days}
            onChange={(next) => {
              setDays(next)
              setDirty(true)
            }}
            exerciseOptions={exercisesQuery.data ?? []}
          />
        </div>
      </div>

      <ConfirmDialog
        open={blocker.status === "blocked"}
        title={t("program.dirty")}
        description={t("program.unsaved")}
        confirmLabel={t("common.leave")}
        cancelLabel={t("common.stay")}
        onConfirm={() => blocker.proceed?.()}
        onClose={() => blocker.reset?.()}
      />
    </>
  )
}
