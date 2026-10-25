import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useBlocker, useNavigate } from "@tanstack/react-router"
import {
  Archive,
  Bookmark,
  ClipboardCheck,
  Eye,
  Printer,
  Save,
  Send,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { getApiErrorDetail, getApiStatus, translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type AthleteDetail,
  AthletesService,
  type DayInput,
  ExercisesService,
  ProgramsService,
  type ProgramVersionDetail,
} from "@/client"
import { DateField } from "@/components/DateField"
import {
  Button,
  Card,
  ConfirmDialog,
  Dialog,
  ErrorState,
  PageHeader,
  Spinner,
  StatusBadge,
  TextField,
} from "@/components/M3"
import { ProgramStructureEditor } from "@/components/ProgramStructureEditor"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function ProgramEditorPage({ versionId }: { versionId: string }) {
  const { t, formatNumber } = useI18n()
  const { activeGym, activeGymId, isAdmin, activeRole } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [meta, setMeta] = useState({
    title: "",
    goal: "",
    notes: "",
    start_date: null as string | null,
    end_date: null as string | null,
  })
  const [days, setDays] = useState<DayInput[]>([])
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [publishOpen, setPublishOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [templateOpen, setTemplateOpen] = useState(false)
  const [templateForm, setTemplateForm] = useState({
    name: "",
    goal: "",
    notes: "",
  })

  const versionQuery = useQuery({
    queryKey: ["program-version", activeGymId, versionId],
    queryFn: async () =>
      (
        await ProgramsService.readProgramVersion({
          path: { version_id: versionId },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })

  const exercisesQuery = useQuery({
    queryKey: ["exercises", activeGymId, "builder"],
    queryFn: async () =>
      (await ExercisesService.listExercises({ query: { q: "" } })).data.data,
    enabled: Boolean(activeGymId),
  })

  const version = versionQuery.data
  const athleteQuery = useQuery({
    queryKey: ["athlete", activeGymId, version?.athlete_user_id],
    queryFn: async (): Promise<AthleteDetail> =>
      (
        await AthletesService.readAthlete({
          path: { athlete_user_id: version!.athlete_user_id },
        })
      ).data,
    enabled: Boolean(activeGymId && version?.athlete_user_id),
  })
  const trainedDaysCount = athleteQuery.data?.profile.training_days_count
  const canEdit =
    !athleteQuery.data?.profile.is_archived &&
    (version?.status === "DRAFT" || version?.status === "ACTIVE") &&
    (isAdmin || activeRole === "COACH")
  const shouldBlock = useMemo(() => dirty && canEdit, [dirty, canEdit])
  const blocker = useBlocker({
    shouldBlockFn: () => shouldBlock,
    withResolver: true,
    disabled: !shouldBlock,
  })

  const loadedVersion = useRef<string | null>(null)

  const applyVersionToForm = useCallback((next: ProgramVersionDetail) => {
    setError(null)
    setConflict(false)
    setPublishOpen(false)
    setArchiveOpen(false)
    setTemplateOpen(false)
    setMeta({
      title: next.title,
      goal: next.goal ?? "",
      notes: next.notes ?? "",
      start_date: next.start_date ?? null,
      end_date: next.end_date ?? null,
    })
    setDays(next.days as DayInput[])
    setDirty(false)
  }, [])

  useEffect(() => {
    if (!version || loadedVersion.current === version.id) return
    loadedVersion.current = version.id
    applyVersionToForm(version)
  }, [version, applyVersionToForm])

  if (!activeGym) {
    return (
      <PageHeader
        title={t("program.builderTitle")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  if (versionQuery.isLoading) return <Spinner label={t("common.loading")} />
  if (versionQuery.isError || !version) {
    return (
      <ErrorState
        message={translateApiError(versionQuery.error, t)}
        onRetry={() => versionQuery.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  const athleteUserId = version.athlete_user_id
  const currentRevision = version.revision

  function updateMeta(patch: Partial<typeof meta>) {
    setMeta((current) => ({ ...current, ...patch }))
    setDirty(true)
  }

  function updateDays(next: DayInput[]) {
    setDays(next)
    setDirty(true)
  }

  async function reloadLatest() {
    const result = await versionQuery.refetch()
    if (!result.data) return
    loadedVersion.current = result.data.id
    queryClient.setQueryData(
      ["program-version", activeGymId, versionId],
      result.data,
    )
    applyVersionToForm(result.data)
  }

  async function saveDraft(showMessage = true): Promise<boolean> {
    if (!meta.title.trim()) {
      setError(t("validation.title"))
      return false
    }
    if (meta.start_date && meta.end_date && meta.end_date < meta.start_date) {
      setError(t("validation.endDate"))
      return false
    }
    setSaving(true)
    setError(null)
    setConflict(false)
    try {
      const response = await ProgramsService.updateProgramVersion({
        path: { version_id: versionId },
        body: {
          title: meta.title.trim(),
          goal: meta.goal || null,
          notes: meta.notes || null,
          start_date: meta.start_date,
          end_date: meta.end_date,
          days,
          expected_revision: currentRevision,
        },
      })
      queryClient.setQueryData(
        ["program-version", activeGymId, versionId],
        response.data,
      )
      await queryClient.invalidateQueries({
        queryKey: ["programs", activeGymId, athleteUserId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["print-version", activeGymId, versionId],
      })
      setDirty(false)
      if (showMessage) show(t("program.saved"), "success")
      return true
    } catch (err) {
      setConflict(
        getApiStatus(err) === 409 &&
          getApiErrorDetail(err) === "program_version_conflict",
      )
      setError(translateApiError(err, t))
      return false
    } finally {
      setSaving(false)
    }
  }

  async function publish() {
    if (dirty && !(await saveDraft(false))) return
    setSaving(true)
    setError(null)
    try {
      await ProgramsService.publishProgramVersion({
        path: { version_id: versionId },
      })
      await queryClient.invalidateQueries({
        queryKey: ["programs", activeGymId, athleteUserId],
      })
      show(t("program.published"), "success")
      setPublishOpen(false)
      navigate({
        to: "/gyms/$gymId/athletes/$athleteId",
        params: { gymId: activeGymId!, athleteId: athleteUserId },
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function archive() {
    setSaving(true)
    setError(null)
    try {
      await ProgramsService.archiveProgramVersion({
        path: { version_id: versionId },
      })
      await queryClient.invalidateQueries({
        queryKey: ["programs", activeGymId, athleteUserId],
      })
      show(t("program.archivedMessage"), "success")
      setArchiveOpen(false)
      navigate({
        to: "/gyms/$gymId/athletes/$athleteId",
        params: { gymId: activeGymId!, athleteId: athleteUserId },
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function saveTemplate() {
    if (dirty && !(await saveDraft(false))) return
    if (!templateForm.name.trim()) {
      setError(t("validation.title"))
      return
    }
    setSaving(true)
    setError(null)
    try {
      await ProgramsService.saveAsTemplate({
        path: { version_id: versionId },
        body: {
          name: templateForm.name.trim(),
          goal: templateForm.goal || null,
          notes: templateForm.notes || null,
        },
      })
      await queryClient.invalidateQueries({
        queryKey: ["templates", activeGymId],
      })
      setTemplateOpen(false)
      setTemplateForm({ name: "", goal: "", notes: "" })
      show(t("program.templateSaved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  const backTo = () => {
    if (activeRole === "ATHLETE") {
      navigate({
        to: "/gyms/$gymId/my",
        params: { gymId: activeGymId! },
      })
      return
    }
    navigate({
      to: "/gyms/$gymId/athletes/$athleteId",
      params: { gymId: activeGymId!, athleteId: athleteUserId },
    })
  }

  return (
    <>
      <PageHeader
        title={meta.title || t("program.builderTitle")}
        subtitle={`${version.athlete_name ?? ""} · ${activeGym.name} · ${t(
          "program.versionLabel",
          {
            version: formatNumber(version.version_number),
          },
        )}`}
        onBack={backTo}
        backLabel={t("common.back")}
        actions={
          <>
            <StatusBadge status={version.status.toLowerCase()} />
            {version.status !== "DRAFT" ? (
              <Button
                variant="outlined"
                icon={<Printer size={16} />}
                onClick={() => window.open(`/print/${version.id}`, "_blank")}
              >
                {t("common.print")}
              </Button>
            ) : null}
            {canEdit &&
            version.status === "ACTIVE" &&
            activeRole !== "ATHLETE" ? (
              <Button
                variant="outlined"
                icon={<Archive size={16} />}
                onClick={() => setArchiveOpen(true)}
              >
                {t("program.archive")}
              </Button>
            ) : null}
          </>
        }
      />

      {version.status === "DRAFT" ? (
        <div className="m3-banner">
          <Eye size={18} />
          <span>{t("program.draftBanner")}</span>
        </div>
      ) : version.status === "ACTIVE" ? (
        <div className="m3-banner m3-banner--active">
          <ClipboardCheck size={18} />
          <span>{t("program.activeBanner")}</span>
        </div>
      ) : (
        <div className="m3-banner m3-banner--archived">
          <Archive size={18} />
          <span>{t("program.archiveBanner")}</span>
        </div>
      )}

      {error ? (
        <div className="m3-inline-alert" style={{ marginBottom: 14 }}>
          <span>{error}</span>
          {conflict ? (
            <Button variant="text" onClick={() => void reloadLatest()}>
              {t("program.reloadLatest")}
            </Button>
          ) : null}
        </div>
      ) : null}

      <div className="m3-builder-layout">
        <div className="m3-builder-meta">
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("program.title")}</h2>
                <p className="m3-section__subtitle">
                  {version.athlete_name} · {version.coach_name ?? ""}
                </p>
              </div>
            </div>
            <div className="stack">
              <TextField
                label={t("program.titleLabel")}
                value={meta.title}
                onChange={(event) => updateMeta({ title: event.target.value })}
                disabled={!canEdit}
                required
              />
              <TextField
                label={t("program.goal")}
                value={meta.goal}
                onChange={(event) => updateMeta({ goal: event.target.value })}
                disabled={!canEdit}
              />
              <div className="grid-2">
                <DateField
                  label={t("program.startDate")}
                  value={meta.start_date}
                  maxValue={meta.end_date}
                  onChange={(value) => updateMeta({ start_date: value })}
                  disabled={!canEdit}
                />
                <DateField
                  label={t("program.endDate")}
                  value={meta.end_date}
                  minValue={meta.start_date}
                  onChange={(value) => updateMeta({ end_date: value })}
                  disabled={!canEdit}
                />
              </div>
              <TextField
                label={t("program.notes")}
                value={meta.notes}
                onChange={(event) => updateMeta({ notes: event.target.value })}
                multiline
                rows={4}
                disabled={!canEdit}
              />
            </div>
          </Card>
        </div>

        <div>
          <div className="row row--between" style={{ marginBottom: 12 }}>
            <div>
              <h2>{t("program.days")}</h2>
              <p className="muted" style={{ fontSize: 12 }}>
                {dirty ? (
                  <>
                    {t("program.dirty")}
                    <span className="m3-dirty-dot" />
                  </>
                ) : (
                  t("program.lastSaved")
                )}
              </p>
            </div>
          </div>
          <ProgramStructureEditor
            days={days}
            onChange={updateDays}
            exerciseOptions={exercisesQuery.data ?? []}
            trainedDaysCount={trainedDaysCount}
            readOnly={!canEdit}
          />
        </div>
      </div>

      {canEdit ? (
        <div className="m3-builder-actions">
          <Button
            variant="text"
            icon={<Bookmark size={16} />}
            onClick={() => {
              setTemplateForm({
                name: meta.title,
                goal: meta.goal,
                notes: meta.notes,
              })
              setTemplateOpen(true)
            }}
          >
            {t("program.saveAsTemplate")}
          </Button>
          <Button
            variant="text"
            icon={<Archive size={16} />}
            onClick={() => setArchiveOpen(true)}
          >
            {t("program.archive")}
          </Button>
          <div className="m3-builder-actions__spacer" />
          <Button
            variant="outlined"
            icon={<Save size={16} />}
            onClick={() => void saveDraft()}
            loading={saving}
            disabled={!dirty}
          >
            {version.status === "ACTIVE"
              ? t("common.save")
              : t("program.saveDraft")}
          </Button>
          {version.status === "DRAFT" ? (
            <Button
              icon={<Send size={16} />}
              onClick={() => setPublishOpen(true)}
            >
              {t("program.publish")}
            </Button>
          ) : null}
        </div>
      ) : null}

      <ConfirmDialog
        open={publishOpen}
        title={t("program.publishTitle")}
        description={`${t("program.publishConfirm")} ${t("program.publishEmpty")}`}
        confirmLabel={t("program.publish")}
        cancelLabel={t("common.cancel")}
        onConfirm={publish}
        onClose={() => setPublishOpen(false)}
        loading={saving}
      />

      <ConfirmDialog
        open={archiveOpen}
        title={t("program.archiveTitle")}
        description={t("program.archiveConfirm")}
        confirmLabel={t("program.archive")}
        cancelLabel={t("common.cancel")}
        onConfirm={archive}
        onClose={() => setArchiveOpen(false)}
        destructive
        loading={saving}
      />

      <Dialog
        open={templateOpen}
        title={t("program.saveAsTemplate")}
        description={t("templates.copyNote")}
        onClose={() => setTemplateOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setTemplateOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={saveTemplate} loading={saving}>
              {t("program.saveAsTemplate")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <TextField
            label={t("program.templateName")}
            value={templateForm.name}
            onChange={(event) =>
              setTemplateForm({ ...templateForm, name: event.target.value })
            }
            required
          />
          <TextField
            label={t("program.goal")}
            value={templateForm.goal}
            onChange={(event) =>
              setTemplateForm({ ...templateForm, goal: event.target.value })
            }
          />
          <TextField
            label={t("program.notes")}
            value={templateForm.notes}
            onChange={(event) =>
              setTemplateForm({ ...templateForm, notes: event.target.value })
            }
            multiline
            rows={3}
          />
        </div>
      </Dialog>

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
