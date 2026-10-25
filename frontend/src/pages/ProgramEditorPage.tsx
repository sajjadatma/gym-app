import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useBlocker, useNavigate } from "@tanstack/react-router"
import {
  Archive,
  ArrowLeft,
  Bookmark,
  Building2,
  CalendarRange,
  CheckCircle2,
  Circle,
  ClipboardCheck,
  Eye,
  Printer,
  Save,
  Send,
  Sparkles,
  UserRound,
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
  ConfirmDialog,
  Dialog,
  ErrorState,
  Spinner,
  StatusBadge,
  TextField,
} from "@/components/M3"
import { ProgramStructureEditor } from "@/components/ProgramStructureEditor"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function ProgramEditorPage({ versionId }: { versionId: string }) {
  const { t, formatNumber, formatDate } = useI18n()
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
  const [mobilePanel, setMobilePanel] = useState<"days" | "details">("days")
  const [templateForm, setTemplateForm] = useState({
    name: "",
    goal: "",
    notes: "",
  })
  const errorRef = useRef<HTMLDivElement>(null)

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

  useEffect(() => {
    if (error) errorRef.current?.focus()
  }, [error])

  const totalExercises = days.reduce(
    (total, day) => total + day.exercises.length,
    0,
  )
  const totalSets = days.reduce(
    (total, day) =>
      total +
      day.exercises.reduce((sets, exercise) => sets + exercise.sets.length, 0),
    0,
  )
  const dateRange =
    meta.start_date || meta.end_date
      ? `${formatDate(meta.start_date)} — ${formatDate(meta.end_date)}`
      : t("program.noDateRange")
  const checklist = [
    { label: t("program.titleLabel"), done: Boolean(meta.title.trim()) },
    { label: t("program.days"), done: days.length > 0 },
    { label: t("program.metricExercises"), done: totalExercises > 0 },
    { label: t("program.metricSets"), done: totalSets > 0 },
  ]

  if (!activeGym) {
    return (
      <div className="program-studio program-studio--empty">
        <h1>{t("program.builderTitle")}</h1>
        <p className="muted">{t("context.noGymHint")}</p>
      </div>
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
      <div className="program-studio">
        <div className="program-studio__commandbar">
          <button
            type="button"
            className="program-studio__back"
            onClick={backTo}
            aria-label={t("common.back")}
            title={t("common.back")}
          >
            <ArrowLeft size={18} aria-hidden />
          </button>
          <div className="program-studio__command-title">
            <span>{t("program.studio")}</span>
            <strong>{meta.title || t("program.builderTitle")}</strong>
          </div>
          <div className="program-studio__command-status">
            <StatusBadge status={version.status.toLowerCase()} />
            {dirty && canEdit ? (
              <span className="program-studio__dirty">
                <span className="m3-dirty-dot" />
                {t("program.dirty")}
              </span>
            ) : (
              <span className="program-studio__saved">
                {t("program.lastSaved")}
              </span>
            )}
          </div>
          <div className="program-studio__command-actions">
            {version.status !== "DRAFT" ? (
              <Button
                variant="text"
                icon={<Printer size={16} />}
                className="program-studio__secondary-action"
                onClick={() => window.open(`/print/${version.id}`, "_blank")}
              >
                {t("common.print")}
              </Button>
            ) : null}
            {canEdit && version.status === "ACTIVE" ? (
              <Button
                variant="text"
                icon={<Archive size={16} />}
                className="program-studio__secondary-action"
                onClick={() => setArchiveOpen(true)}
              >
                {t("program.archive")}
              </Button>
            ) : null}
            {canEdit ? (
              <Button
                variant="text"
                icon={<Bookmark size={16} />}
                className="program-studio__secondary-action"
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
            ) : null}
            {canEdit ? (
              <Button
                variant="outlined"
                icon={<Save size={16} />}
                onClick={() => void saveDraft()}
                loading={saving}
                disabled={!dirty}
                className="program-studio__save"
              >
                {version.status === "ACTIVE"
                  ? t("common.save")
                  : t("program.saveDraft")}
              </Button>
            ) : null}
            {canEdit && version.status === "DRAFT" ? (
              <Button
                icon={<Send size={16} />}
                onClick={() => setPublishOpen(true)}
                className="program-studio__publish"
              >
                {t("program.publish")}
              </Button>
            ) : null}
          </div>
        </div>

        <header className="program-studio__hero">
          <div className="program-studio__hero-copy">
            <div className="program-studio__eyebrow">
              <Sparkles size={14} aria-hidden />
              <span>{t("program.studio")}</span>
              <span className="program-studio__eyebrow-divider" />
              <span>
                {t("program.versionLabel", {
                  version: formatNumber(version.version_number),
                })}
              </span>
            </div>
            <h1>{meta.title || t("program.builderTitle")}</h1>
            <div className="program-studio__hero-meta">
              <span>
                <UserRound size={14} aria-hidden />
                {version.athlete_name}
              </span>
              <span>
                <Building2 size={14} aria-hidden />
                {activeGym.name}
              </span>
              {version.coach_name ? (
                <span>
                  {t("program.coach")}: {version.coach_name}
                </span>
              ) : null}
            </div>
          </div>
          <div className="program-studio__metrics">
            <div className="program-studio__metric">
              <span>{t("program.days")}</span>
              <strong>{formatNumber(days.length)}</strong>
            </div>
            <div className="program-studio__metric">
              <span>{t("program.metricExercises")}</span>
              <strong>{formatNumber(totalExercises)}</strong>
            </div>
            <div className="program-studio__metric">
              <span>{t("program.metricSets")}</span>
              <strong>{formatNumber(totalSets)}</strong>
            </div>
            <div className="program-studio__metric program-studio__metric--wide">
              <span>
                <CalendarRange size={12} aria-hidden /> {t("program.startDate")}{" "}
                — {t("program.endDate")}
              </span>
              <strong>{dateRange}</strong>
            </div>
          </div>
        </header>

        <div
          className={`program-studio__notice is-${version.status.toLowerCase()}`}
        >
          {version.status === "DRAFT" ? (
            <Eye size={17} aria-hidden />
          ) : version.status === "ACTIVE" ? (
            <ClipboardCheck size={17} aria-hidden />
          ) : (
            <Archive size={17} aria-hidden />
          )}
          <span>
            {version.status === "DRAFT"
              ? t("program.draftBanner")
              : version.status === "ACTIVE"
                ? t("program.activeBanner")
                : t("program.archiveBanner")}
          </span>
        </div>

        {error ? (
          <div
            ref={errorRef}
            className="program-studio__error"
            role="alert"
            tabIndex={-1}
          >
            <span>{error}</span>
            {conflict ? (
              <Button variant="text" onClick={() => void reloadLatest()}>
                {t("program.reloadLatest")}
              </Button>
            ) : null}
          </div>
        ) : null}

        <div className="program-studio__mobile-switch">
          <button
            type="button"
            className={mobilePanel === "days" ? "is-active" : ""}
            aria-pressed={mobilePanel === "days"}
            onClick={() => setMobilePanel("days")}
          >
            {t("program.days")}
          </button>
          <button
            type="button"
            className={mobilePanel === "details" ? "is-active" : ""}
            aria-pressed={mobilePanel === "details"}
            onClick={() => setMobilePanel("details")}
          >
            {t("program.details")}
          </button>
        </div>

        <div
          className={`program-studio__workspace ${
            mobilePanel === "details" ? "show-details" : "show-days"
          }`}
        >
          <ProgramStructureEditor
            days={days}
            onChange={updateDays}
            exerciseOptions={exercisesQuery.data ?? []}
            trainedDaysCount={trainedDaysCount}
            readOnly={!canEdit}
          />

          <aside
            className="program-studio__inspector"
            aria-label={t("program.details")}
          >
            <section className="program-inspector__section">
              <div className="program-inspector__heading">
                <span aria-hidden>01</span>
                <h2>{t("program.details")}</h2>
              </div>
              <div className="program-inspector__fields">
                <TextField
                  label={t("program.titleLabel")}
                  value={meta.title}
                  onChange={(event) =>
                    updateMeta({ title: event.target.value })
                  }
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
                  onChange={(event) =>
                    updateMeta({ notes: event.target.value })
                  }
                  multiline
                  rows={4}
                  disabled={!canEdit}
                />
              </div>
            </section>

            <section className="program-inspector__section">
              <div className="program-inspector__heading">
                <span aria-hidden>02</span>
                <h2>{t("program.athlete")}</h2>
              </div>
              <div className="program-inspector__athlete">
                <span className="program-inspector__avatar" aria-hidden>
                  <UserRound size={18} />
                </span>
                <div>
                  <strong>{version.athlete_name}</strong>
                  <span>
                    {t("program.coach")}: {version.coach_name ?? "—"}
                  </span>
                </div>
              </div>
              <dl className="program-inspector__facts">
                <div>
                  <dt>{t("athletes.trainingDays")}</dt>
                  <dd>{formatNumber(trainedDaysCount)}</dd>
                </div>
                <div>
                  <dt>{t("program.startDate")}</dt>
                  <dd>{formatDate(meta.start_date)}</dd>
                </div>
                <div>
                  <dt>{t("program.endDate")}</dt>
                  <dd>{formatDate(meta.end_date)}</dd>
                </div>
              </dl>
            </section>

            <section className="program-inspector__section">
              <div className="program-inspector__heading">
                <span aria-hidden>03</span>
                <h2>{t("program.publishChecklist")}</h2>
              </div>
              <ul className="program-inspector__checklist">
                {checklist.map((item) => (
                  <li key={item.label} className={item.done ? "is-done" : ""}>
                    {item.done ? (
                      <CheckCircle2 size={16} aria-hidden />
                    ) : (
                      <Circle size={16} aria-hidden />
                    )}
                    <span>{item.label}</span>
                  </li>
                ))}
              </ul>
              <p className="program-inspector__hint">
                {checklist.every((item) => item.done)
                  ? t("program.publishConfirm")
                  : t("program.publishEmpty")}
              </p>
            </section>

            <section className="program-inspector__section program-inspector__mobile-actions">
              <div className="program-inspector__heading">
                <span aria-hidden>04</span>
                <h2>{t("common.actions")}</h2>
              </div>
              <div className="program-inspector__action-list">
                {version.status !== "DRAFT" ? (
                  <Button
                    variant="outlined"
                    icon={<Printer size={16} />}
                    onClick={() =>
                      window.open(`/print/${version.id}`, "_blank")
                    }
                  >
                    {t("common.print")}
                  </Button>
                ) : null}
                {canEdit && version.status === "ACTIVE" ? (
                  <Button
                    variant="outlined"
                    icon={<Archive size={16} />}
                    onClick={() => setArchiveOpen(true)}
                  >
                    {t("program.archive")}
                  </Button>
                ) : null}
                {canEdit ? (
                  <Button
                    variant="outlined"
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
                ) : null}
              </div>
            </section>
          </aside>
        </div>
      </div>

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
