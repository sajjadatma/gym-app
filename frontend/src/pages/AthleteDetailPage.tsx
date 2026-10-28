import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useBlocker, useNavigate } from "@tanstack/react-router"
import {
  Archive,
  ArrowLeft,
  CalendarDays,
  ChevronDown,
  ClipboardList,
  Download,
  FileUp,
  History,
  Mail,
  Pencil,
  Phone,
  Plus,
  Printer,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldAlert,
  Sparkles,
  Trash2,
  UserRound,
} from "lucide-react"
import { type ReactNode, useEffect, useId, useRef, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  type AthleteDetail,
  AthletesService,
  type CoachPublic,
  GymsService,
  ProgramsService,
  type ProgramVersionDetail,
  type ProgramVersionSummary,
} from "@/client"
import { client } from "@/client/client.gen"
import { AsyncPickerField } from "@/components/AsyncPickerField"
import { DateField } from "@/components/DateField"
import { DeleteAthletesDialog } from "@/components/DeleteAthletesDialog"
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
  Tabs,
  TextField,
} from "@/components/M3"
import { type RowActionItem, RowActionMenu } from "@/components/RowActionMenu"
import { type TranslationKey, useI18n } from "@/i18n"
import { MAX_UPLOAD_BYTES } from "@/lib/upload"
import { useAsyncPicker } from "@/lib/use-async-picker"
import { useSnackbar } from "@/snackbar"

type Tab = "profile" | "programs" | "bodyFiles"

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function profileFormValues(athlete: AthleteDetail) {
  return {
    full_name: athlete.profile.full_name ?? "",
    phone: athlete.profile.phone ?? "",
    birth_date: athlete.profile.birth_date ?? null,
    height_cm: athlete.profile.height_cm?.toString() ?? "",
    weight_kg: athlete.profile.weight_kg?.toString() ?? "",
    chest_cm: athlete.profile.chest_cm?.toString() ?? "",
    waist_cm: athlete.profile.waist_cm?.toString() ?? "",
    hips_cm: athlete.profile.hips_cm?.toString() ?? "",
    arm_cm: athlete.profile.arm_cm?.toString() ?? "",
    thigh_cm: athlete.profile.thigh_cm?.toString() ?? "",
    training_goal: athlete.profile.training_goal ?? "",
    sports_history: athlete.profile.sports_history ?? "",
    fitness_level: athlete.profile.fitness_level ?? "",
    limitations: athlete.profile.limitations ?? "",
    training_days_count: athlete.profile.training_days_count?.toString() ?? "",
    equipment: athlete.profile.equipment ?? "",
    internal_coach_note: athlete.internal_coach_note ?? "",
  }
}

function ReadOnlyField({
  label,
  value,
  wide,
  className = "",
}: {
  label: string
  value: ReactNode
  wide?: boolean
  className?: string
}) {
  return (
    <div
      className={`m3-readonly-field ${wide ? "m3-readonly-field--wide" : ""} ${className}`}
    >
      <span className="m3-readonly-field__label">{label}</span>
      <span className="m3-readonly-field__value">{value}</span>
    </div>
  )
}

function ProgramReviewDetail({ version }: { version: ProgramVersionDetail }) {
  const { t, formatDate, formatNumber } = useI18n()
  return (
    <div className="program-review">
      {version.goal || version.notes ? (
        <div className="program-review__meta">
          {version.goal ? (
            <span>
              <strong>{t("program.goal")}:</strong> {version.goal}
            </span>
          ) : null}
          {version.notes ? (
            <span>
              <strong>{t("program.notes")}:</strong> {version.notes}
            </span>
          ) : null}
        </div>
      ) : null}

      {version.days.length === 0 ? (
        <p className="muted">{t("program.noDays")}</p>
      ) : (
        version.days.map((day, dayIndex) => (
          <section
            key={day.id ?? `${day.day_number}-${dayIndex}`}
            className="program-review__day"
          >
            <div className="program-review__day-head">
              <h4>
                {t("program.day")}{" "}
                {formatNumber(day.day_number || dayIndex + 1)}
                {" · "}
                {day.title}
              </h4>
              {day.weekday ? (
                <span className="muted">
                  {t(`weekday.${day.weekday}` as TranslationKey)}
                </span>
              ) : null}
            </div>
            {day.category_names?.length ? (
              <div className="row" style={{ gap: 4 }}>
                {day.category_names.map((name) => (
                  <span key={name} className="m3-chip">
                    {name}
                  </span>
                ))}
              </div>
            ) : null}
            {day.notes ? (
              <p className="program-review__note">{day.notes}</p>
            ) : null}
            {day.exercises.length === 0 ? (
              <p className="muted">{t("program.noExercises")}</p>
            ) : (
              day.exercises.map((exercise, exerciseIndex) => (
                <article
                  key={
                    exercise.id ?? `${exercise.exercise_id}-${exerciseIndex}`
                  }
                  className="program-review__exercise"
                >
                  <div className="program-review__exercise-head">
                    <strong>
                      {formatNumber(exerciseIndex + 1)}.{" "}
                      {exercise.exercise_name}
                    </strong>
                    <span className="muted">{exercise.muscle_group}</span>
                  </div>
                  {exercise.notes ? (
                    <p className="program-review__note">{exercise.notes}</p>
                  ) : null}
                  {exercise.sets.length === 0 ? (
                    <p className="muted">{t("program.noSets")}</p>
                  ) : (
                    <div className="program-review__sets-wrap">
                      <table className="program-review__sets">
                        <thead>
                          <tr>
                            <th>{t("print.set")}</th>
                            <th>{t("print.reps")}</th>
                            <th>{t("print.weight")}</th>
                            <th>{t("print.rest")}</th>
                            <th>{t("program.duration")}</th>
                            <th>{t("program.intensity")}</th>
                            <th>{t("print.notes")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {exercise.sets.map((set, setIndex) => (
                            <tr key={set.id ?? setIndex}>
                              <td>{formatNumber(set.set_number)}</td>
                              <td>
                                {set.reps_min == null && set.reps_max == null
                                  ? "—"
                                  : set.reps_min === set.reps_max
                                    ? formatNumber(set.reps_min)
                                    : `${formatNumber(
                                        set.reps_min ?? 0,
                                      )}–${formatNumber(set.reps_max ?? 0)}`}
                              </td>
                              <td>
                                {set.weight_kg == null
                                  ? "—"
                                  : `${formatNumber(set.weight_kg)} ${t(
                                      "common.units.kg",
                                    )}`}
                              </td>
                              <td>
                                {set.rest_seconds == null
                                  ? "—"
                                  : `${formatNumber(
                                      set.rest_seconds,
                                    )} ${t("common.units.seconds")}`}
                              </td>
                              <td>
                                {set.duration_seconds == null
                                  ? "—"
                                  : `${formatNumber(
                                      set.duration_seconds,
                                    )} ${t("common.units.seconds")}`}
                              </td>
                              <td>{set.intensity || "—"}</td>
                              <td>{set.note || "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </article>
              ))
            )}
          </section>
        ))
      )}
      {version.end_date ? (
        <p className="muted program-review__footer">
          {t("program.endDate")}: {formatDate(version.end_date)}
        </p>
      ) : null}
    </div>
  )
}

function ProgramReviewCard({
  version,
  defaultOpen,
  canEdit,
  onEdit,
  onPrint,
  onDelete,
}: {
  version: ProgramVersionSummary
  defaultOpen: boolean
  canEdit: boolean
  onEdit: () => void
  onPrint: () => void
  onDelete: () => void
}) {
  const { t, formatDate, formatNumber } = useI18n()
  const { activeGymId } = useAuth()
  const [open, setOpen] = useState(defaultOpen)
  const panelId = `program-review-${version.id}`

  useEffect(() => {
    if (defaultOpen) setOpen(true)
  }, [defaultOpen])

  const detailQuery = useQuery({
    queryKey: ["program-review", activeGymId, version.id],
    queryFn: async () =>
      (
        await ProgramsService.readProgramVersion({
          path: { version_id: version.id },
        })
      ).data,
    enabled: Boolean(activeGymId && open),
    staleTime: 30_000,
  })

  return (
    <article
      className={`m3-version-row program-review-card ${open ? "is-open" : ""}`}
    >
      <div className="program-review-card__summary">
        <button
          type="button"
          className="program-review-card__toggle"
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={`${version.title} — ${
            open ? t("athletes.collapseProgram") : t("athletes.expandProgram")
          }`}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="program-review-card__chevron" aria-hidden>
            <ChevronDown size={18} />
          </span>
          <ClipboardList size={19} className="muted" aria-hidden />
          <span className="program-review-card__text">
            <span className="program-review-card__title">
              {version.title}{" "}
              <span className="muted">
                ·{" "}
                {t("program.versionLabel", {
                  version: formatNumber(version.version_number),
                })}
              </span>
            </span>
            <span className="program-review-card__meta">
              <span>
                {t("program.days")}: {formatNumber(version.day_count ?? 0)}
              </span>
              {version.coach_name ? <span>{version.coach_name}</span> : null}
              <span>
                {version.start_date
                  ? t("program.startDate") +
                    ": " +
                    formatDate(version.start_date)
                  : t("program.versionHistory") +
                    ": " +
                    formatDate(version.created_at)}
              </span>
            </span>
          </span>
        </button>
        <div className="program-review-card__actions">
          <StatusBadge status={version.status.toLowerCase()} />
          <Button variant="text" size="sm" onClick={onEdit}>
            {version.status !== "ARCHIVED" && canEdit
              ? t("common.edit")
              : t("common.open")}
          </Button>
          {version.status !== "DRAFT" ? (
            <Button
              variant="text"
              size="sm"
              icon={<Printer size={14} />}
              onClick={onPrint}
            >
              {t("common.print")}
            </Button>
          ) : null}
          {canEdit ? (
            <Button
              variant="text"
              size="sm"
              icon={<Trash2 size={14} />}
              onClick={onDelete}
            >
              {t("common.delete")}
            </Button>
          ) : null}
        </div>
      </div>
      {open ? (
        <section
          id={panelId}
          className="program-review-card__body"
          aria-label={t("athletes.programReview")}
        >
          {detailQuery.isLoading ? (
            <Spinner label={t("common.loading")} />
          ) : detailQuery.isError || !detailQuery.data ? (
            <ErrorState
              message={translateApiError(detailQuery.error, t)}
              onRetry={() => detailQuery.refetch()}
              retryLabel={t("common.retry")}
            />
          ) : (
            <ProgramReviewDetail version={detailQuery.data} />
          )}
        </section>
      ) : null}
    </article>
  )
}

export function AthleteDetailPage({ athleteId }: { athleteId: string }) {
  const { t, formatDate, formatDateTime, formatNumber } = useI18n()
  const { activeGym, activeGymId, isAdmin, activeRole, me } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [tab, setTab] = useState<Tab>("programs")
  const [editingProfile, setEditingProfile] = useState(false)
  const [profileDirty, setProfileDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [reassignOpen, setReassignOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [programOpen, setProgramOpen] = useState(false)
  const [newCoachId, setNewCoachId] = useState("")
  const [programTitle, setProgramTitle] = useState("")
  const [programGoal, setProgramGoal] = useState("")
  const [programStart, setProgramStart] = useState<string | null>(null)
  const [programEnd, setProgramEnd] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] =
    useState<ProgramVersionSummary | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const hydratedProfileRef = useRef<string | null>(null)
  const uploadId = useId()
  const [form, setForm] = useState(() => ({
    full_name: "",
    phone: "",
    birth_date: "" as string | null,
    height_cm: "",
    weight_kg: "",
    chest_cm: "",
    waist_cm: "",
    hips_cm: "",
    arm_cm: "",
    thigh_cm: "",
    training_goal: "",
    sports_history: "",
    fitness_level: "",
    limitations: "",
    training_days_count: "",
    equipment: "",
    internal_coach_note: "",
  }))

  const blocker = useBlocker({
    shouldBlockFn: () => profileDirty && editingProfile,
    withResolver: true,
    disabled: !(profileDirty && editingProfile),
  })

  useEffect(() => {
    if (!profileDirty) return
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ""
    }
    window.addEventListener("beforeunload", beforeUnload)
    return () => window.removeEventListener("beforeunload", beforeUnload)
  }, [profileDirty])

  const athleteQuery = useQuery({
    queryKey: ["athlete", activeGymId, athleteId],
    queryFn: async () =>
      (
        await AthletesService.readAthlete({
          path: { athlete_user_id: athleteId },
        })
      ).data,
    enabled: Boolean(activeGymId),
    staleTime: 0,
    refetchOnWindowFocus: true,
  })

  const programsQuery = useQuery({
    queryKey: ["programs", activeGymId, athleteId],
    queryFn: async () =>
      (
        await ProgramsService.listPrograms({
          path: { athlete_user_id: athleteId },
        })
      ).data.data,
    enabled: Boolean(activeGymId),
    staleTime: 0,
    refetchOnWindowFocus: true,
  })

  const coachPicker = useAsyncPicker<CoachPublic>({
    queryKey: ["async-gym-coaches", activeGymId],
    enabled: Boolean(reassignOpen && activeGymId && isAdmin),
    resetKey: `${activeGymId ?? ""}|${reassignOpen}`,
    fetchPage: async (search, offset, limit) =>
      (
        await GymsService.listCoaches({
          path: { gym_id: activeGymId! },
          query: { q: search, offset, limit },
        })
      ).data,
  })

  const athlete = athleteQuery.data
  useEffect(() => {
    if (!athlete) return
    const profileKey = `${activeGymId}:${athlete.profile.user_id}`
    if (hydratedProfileRef.current === profileKey) return
    hydratedProfileRef.current = profileKey
    setForm(profileFormValues(athlete))
    setEditingProfile(false)
    setProfileDirty(false)
  }, [activeGymId, athlete])

  if (!activeGym) {
    return (
      <PageHeader
        title={t("athletes.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  if (athleteQuery.isLoading) return <Spinner label={t("common.loading")} />
  if (athleteQuery.isError || !athlete) {
    return (
      <ErrorState
        message={translateApiError(athleteQuery.error, t)}
        onRetry={() => athleteQuery.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  const archived = athlete.profile.is_archived
  const canEdit =
    !archived &&
    (isAdmin || (activeRole === "COACH" && athlete.coach_user_id === me?.id))
  const activeProgram = programsQuery.data?.find(
    (item) => item.status === "ACTIVE",
  )

  function convert(value: string) {
    return value.trim() ? Number(value) : null
  }

  function updateForm(patch: Partial<typeof form>) {
    setForm((previous) => ({ ...previous, ...patch }))
    setProfileDirty(true)
  }

  function startEditingProfile() {
    if (!athlete) return
    setError(null)
    setForm(profileFormValues(athlete))
    setProfileDirty(false)
    setEditingProfile(true)
  }

  function cancelEditingProfile() {
    if (!athlete) return
    setError(null)
    setForm(profileFormValues(athlete))
    setProfileDirty(false)
    setEditingProfile(false)
  }

  async function saveProfile() {
    setSaving(true)
    setError(null)
    try {
      const response = await AthletesService.updateAthlete({
        path: { athlete_user_id: athleteId },
        body: {
          full_name: form.full_name || null,
          phone: form.phone || null,
          birth_date: form.birth_date,
          height_cm: convert(form.height_cm),
          weight_kg: convert(form.weight_kg),
          chest_cm: convert(form.chest_cm),
          waist_cm: convert(form.waist_cm),
          hips_cm: convert(form.hips_cm),
          arm_cm: convert(form.arm_cm),
          thigh_cm: convert(form.thigh_cm),
          training_goal: form.training_goal || null,
          sports_history: form.sports_history || null,
          fitness_level: form.fitness_level || null,
          limitations: form.limitations || null,
          training_days_count: form.training_days_count
            ? Number(form.training_days_count)
            : null,
          equipment: form.equipment || null,
          internal_coach_note: form.internal_coach_note || null,
        },
      })
      queryClient.setQueryData(
        ["athlete", activeGymId, athleteId],
        response.data,
      )
      setEditingProfile(false)
      setProfileDirty(false)
      show(t("athletes.noteSaved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  function openNewProgram() {
    setProgramTitle("")
    setProgramGoal("")
    setProgramStart(null)
    setProgramEnd(null)
    setError(null)
    setProgramOpen(true)
  }

  async function createProgram() {
    if (!programTitle.trim()) {
      setError(t("validation.title"))
      return
    }
    setSaving(true)
    setError(null)
    try {
      const response = await ProgramsService.createProgram({
        path: { athlete_user_id: athleteId },
        body: {
          title: programTitle.trim(),
          goal: programGoal || null,
          start_date: programStart,
          end_date: programEnd,
        },
      })
      setProgramOpen(false)
      setProgramTitle("")
      setProgramGoal("")
      setProgramStart(null)
      setProgramEnd(null)
      await queryClient.invalidateQueries({
        queryKey: ["programs", activeGymId, athleteId],
      })
      navigate({
        to: "/gyms/$gymId/programs/$versionId/edit",
        params: { gymId: activeGymId!, versionId: response.data.id },
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function deleteProgramVersion() {
    if (!deleteTarget) return
    setSaving(true)
    setError(null)
    try {
      await ProgramsService.deleteProgramVersion({
        path: { version_id: deleteTarget.id },
      })
      setDeleteTarget(null)
      await queryClient.invalidateQueries({
        queryKey: ["programs", activeGymId, athleteId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["program-version", activeGymId, deleteTarget.id],
      })
      show(t("program.deleted"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function restoreAthlete() {
    setSaving(true)
    setError(null)
    try {
      const response = await AthletesService.restoreAthlete({
        path: { athlete_user_id: athleteId },
      })
      queryClient.setQueryData(
        ["athlete", activeGymId, athleteId],
        response.data,
      )
      await queryClient.invalidateQueries({
        queryKey: ["athletes", activeGymId],
      })
      show(t("athletes.restored"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function reassignCoach() {
    if (!newCoachId) {
      setError(t("validation.selectCoach"))
      return
    }
    setSaving(true)
    setError(null)
    try {
      await AthletesService.reassignCoach({
        path: { athlete_user_id: athleteId },
        body: { coach_user_id: newCoachId },
      })
      await queryClient.invalidateQueries({
        queryKey: ["athlete", activeGymId, athleteId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["athletes", activeGymId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["coaches", activeGymId],
      })
      setReassignOpen(false)
      setNewCoachId("")
      show(t("athletes.reassigned"), "success")
      if (!isAdmin && athlete?.coach_user_id === me?.id) {
        navigate({
          to: "/gyms/$gymId/athletes",
          params: { gymId: activeGymId! },
        })
      }
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function archiveAthlete() {
    setSaving(true)
    setError(null)
    try {
      await AthletesService.archiveAthlete({
        path: { athlete_user_id: athleteId },
      })
      await queryClient.invalidateQueries({
        queryKey: ["athletes", activeGymId],
      })
      show(t("athletes.archived"), "success")
      navigate({
        to: "/gyms/$gymId/athletes",
        params: { gymId: activeGymId! },
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function uploadFile(file: File) {
    if (file.size > MAX_UPLOAD_BYTES) {
      show(t("validation.fileSize"), "error")
      return
    }
    if (!["application/pdf", "image/jpeg", "image/png"].includes(file.type)) {
      show(t("validation.fileType"), "error")
      return
    }
    setUploading(true)
    try {
      await AthletesService.uploadBodyFile({
        path: { athlete_user_id: athleteId },
        body: { file },
      })
      await queryClient.invalidateQueries({
        queryKey: ["athlete", activeGymId, athleteId],
      })
      show(t("athletes.fileUploaded"), "success")
      if (fileInput.current) fileInput.current.value = ""
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setUploading(false)
    }
  }

  async function downloadFile(fileId: string, name: string) {
    try {
      const response = await client.instance.get(
        `/api/v1/athletes/${athleteId}/body-files/${fileId}/download`,
        { responseType: "blob" },
      )
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = name
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      show(translateApiError(err, t), "error")
    }
  }

  const fitnessLevelLabel = (value: string | null | undefined) => {
    if (value === "beginner") return t("athletes.levelBeginner")
    if (value === "intermediate") return t("athletes.levelIntermediate")
    if (value === "advanced") return t("athletes.levelAdvanced")
    return t("person.notRecorded")
  }

  const measurementFields = [
    {
      label: t("athletes.height"),
      value: athlete.profile.height_cm,
      unit: t("common.units.cm"),
    },
    {
      label: t("athletes.weight"),
      value: athlete.profile.weight_kg,
      unit: t("common.units.kg"),
    },
    {
      label: t("athletes.chest"),
      value: athlete.profile.chest_cm,
      unit: t("common.units.cm"),
    },
    {
      label: t("athletes.waist"),
      value: athlete.profile.waist_cm,
      unit: t("common.units.cm"),
    },
    {
      label: t("athletes.hips"),
      value: athlete.profile.hips_cm,
      unit: t("common.units.cm"),
    },
    {
      label: t("athletes.arm"),
      value: athlete.profile.arm_cm,
      unit: t("common.units.cm"),
    },
    {
      label: t("athletes.thigh"),
      value: athlete.profile.thigh_cm,
      unit: t("common.units.cm"),
    },
  ]

  const notRecorded = t("person.notRecorded")

  const tabItems = [
    {
      value: "programs",
      label: t("athletes.programs"),
      count: programsQuery.data?.length ?? 0,
    },
    { value: "profile", label: t("athletes.profile") },
    {
      value: "bodyFiles",
      label: t("athletes.bodyFiles"),
      count: athlete.body_files.length,
    },
  ]

  const adminActions: RowActionItem[] = []
  if (isAdmin && !athlete.profile.is_archived) {
    adminActions.push({
      key: "reassign",
      label: t("athletes.reassign"),
      icon: <RefreshCw size={15} />,
      onSelect: () => {
        setError(null)
        setReassignOpen(true)
      },
    })
  }
  if (isAdmin) {
    adminActions.push({
      key: "archive",
      label: t(
        athlete.profile.is_archived ? "athletes.restore" : "athletes.archive",
      ),
      icon: athlete.profile.is_archived ? (
        <RotateCcw size={15} />
      ) : (
        <Archive size={15} />
      ),
      onSelect: () => {
        if (athlete.profile.is_archived) void restoreAthlete()
        else setArchiveOpen(true)
      },
    })
    adminActions.push({
      key: "delete",
      label: t("athletes.delete"),
      icon: <Trash2 size={15} />,
      destructive: true,
      separatorBefore: true,
      onSelect: () => setDeleteOpen(true),
    })
  }

  return (
    <>
      <PageHeader
        title={athlete.profile.full_name ?? athlete.profile.email}
        subtitle={`${activeGym.name} · ${athlete.coach_name ?? t("athletes.noCoach")}`}
        onBack={() =>
          navigate({
            to: athlete.profile.is_archived
              ? "/athletes/archived"
              : "/athletes",
          })
        }
        backLabel={t("common.back")}
        actions={
          <>
            {canEdit ? (
              <Button icon={<Plus size={17} />} onClick={openNewProgram}>
                {t("athletes.createProgram")}
              </Button>
            ) : null}
            {adminActions.length ? (
              <RowActionMenu
                items={adminActions}
                label={t("common.moreActions")}
                disabled={saving}
              />
            ) : null}
          </>
        }
      />

      {archived ? (
        <div className="m3-banner m3-banner--archived">
          <Archive size={18} aria-hidden />
          <span>{t("athletes.archivedBanner")}</span>
        </div>
      ) : null}

      <section className="m3-profile-hero">
        <div className="m3-profile-hero__identity">
          <div className="m3-profile-hero__avatar">
            <Avatar name={athlete.profile.full_name ?? athlete.profile.email} />
          </div>
          <div className="m3-profile-hero__info">
            <div className="m3-athlete-summary__meta">
              <StatusBadge
                status={athlete.profile.is_archived ? "archived" : "active"}
              />
              <span className="muted">
                {t("athletes.memberSince", {
                  date: formatDate(athlete.profile.created_at),
                })}
              </span>
            </div>
            <div className="m3-profile-hero__contacts">
              <a
                className="m3-contact-chip"
                href={`mailto:${athlete.profile.email}`}
                dir="ltr"
              >
                <Mail size={14} aria-hidden />
                <span>{athlete.profile.email}</span>
              </a>
              {athlete.profile.phone ? (
                <a
                  className="m3-contact-chip"
                  href={`tel:${athlete.profile.phone}`}
                  dir="ltr"
                >
                  <Phone size={14} aria-hidden />
                  <span>{athlete.profile.phone}</span>
                </a>
              ) : null}
              <span className="m3-contact-chip">
                <UserRound size={14} aria-hidden />
                <span>{athlete.coach_name ?? t("athletes.noCoach")}</span>
              </span>
            </div>
          </div>
        </div>

        <div
          className={`m3-profile-hero__program ${
            activeProgram ? "" : "is-empty"
          }`}
        >
          <span className="m3-profile-hero__eyebrow">
            <ClipboardList size={14} aria-hidden />
            {activeProgram ? t("my.activeProgram") : t("program.title")}
          </span>
          {activeProgram ? (
            <>
              <div className="m3-profile-hero__program-name">
                <span>{activeProgram.title}</span>
                <span className="m3-profile-hero__version">
                  {t("program.versionLabel", {
                    version: formatNumber(activeProgram.version_number),
                  })}
                </span>
              </div>
              <div className="m3-profile-hero__program-meta">
                <span>
                  <ClipboardList size={13} aria-hidden />
                  {t("program.days")}: {formatNumber(activeProgram.day_count)}
                </span>
                {activeProgram.coach_name ? (
                  <span>
                    <UserRound size={13} aria-hidden />
                    {activeProgram.coach_name}
                  </span>
                ) : null}
                {activeProgram.start_date ? (
                  <span>
                    <CalendarDays size={13} aria-hidden />
                    {formatDate(activeProgram.start_date)}
                    {activeProgram.end_date
                      ? ` — ${formatDate(activeProgram.end_date)}`
                      : ""}
                  </span>
                ) : null}
              </div>
              <Button
                icon={<ArrowLeft size={16} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/programs/$versionId/edit",
                    params: {
                      gymId: activeGymId!,
                      versionId: activeProgram.id,
                    },
                  })
                }
              >
                {t("common.open")}
              </Button>
            </>
          ) : (
            <>
              <p className="m3-profile-hero__empty">
                {archived
                  ? t("athletes.archivedProgramHint")
                  : t("athletes.noProgramsHint")}
              </p>
              {canEdit ? (
                <Button icon={<Plus size={16} />} onClick={openNewProgram}>
                  {t("athletes.createProgram")}
                </Button>
              ) : null}
            </>
          )}
        </div>
      </section>

      <div className="m3-athlete-stats">
        <span>
          <ClipboardList size={15} aria-hidden />
          {formatNumber(programsQuery.data?.length ?? 0)}{" "}
          {t("athletes.programs")}
        </span>
        <span>
          <FileUp size={15} aria-hidden />
          {formatNumber(athlete.body_files.length)} {t("athletes.bodyFiles")}
        </span>
        <span>
          <CalendarDays size={15} aria-hidden />
          {athlete.profile.training_days_count == null
            ? t("person.notRecorded")
            : t("athletes.trainingDaysValue", {
                count: formatNumber(athlete.profile.training_days_count),
              })}
        </span>
      </div>

      <Tabs
        tabs={tabItems}
        value={tab}
        onChange={(value) => setTab(value as Tab)}
        idPrefix="athlete-record"
      />

      {error ? (
        <div className="m3-inline-alert" style={{ marginBottom: 14 }}>
          {error}
        </div>
      ) : null}

      {tab === "profile" ? (
        <div
          className={`stack m3-profile-stack ${editingProfile ? "is-editing" : ""}`}
          role="tabpanel"
          id="athlete-record-panel-profile"
          aria-labelledby="athlete-record-tab-profile"
        >
          <div className="m3-profile-toolbar">
            <div>
              <h2 className="m3-section__title">{t("athletes.profile")}</h2>
              <p className="m3-section__subtitle">
                {editingProfile
                  ? t("athletes.editingProfileHint")
                  : t("athletes.profileHint")}
              </p>
            </div>
            {canEdit && !editingProfile ? (
              <Button
                variant="outlined"
                icon={<Pencil size={16} />}
                onClick={startEditingProfile}
              >
                {t("athletes.editProfile")}
              </Button>
            ) : null}
          </div>

          {editingProfile ? (
            <div className="m3-profile-editbar">
              <span>{t("athletes.editingProfile")}</span>
              <div className="row" style={{ gap: 6 }}>
                <Button
                  variant="text"
                  onClick={cancelEditingProfile}
                  disabled={saving}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  icon={<Save size={16} />}
                  onClick={saveProfile}
                  loading={saving}
                >
                  {t("athletes.saveProfile")}
                </Button>
              </div>
            </div>
          ) : null}

          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("athletes.identity")}</h2>
                <p className="m3-section__subtitle">
                  {t("athletes.measurementsUpdated")}:{" "}
                  {formatDateTime(athlete.profile.updated_at)}
                </p>
              </div>
            </div>
            {editingProfile ? (
              <>
                <div className="grid-2">
                  <TextField
                    label={t("athletes.fullName")}
                    value={form.full_name}
                    onChange={(event) =>
                      updateForm({ full_name: event.target.value })
                    }
                  />
                  <TextField
                    label={t("athletes.phone")}
                    dir="ltr"
                    value={form.phone}
                    onChange={(event) =>
                      updateForm({ phone: event.target.value })
                    }
                  />
                </div>
                <div className="grid-2" style={{ marginTop: 14 }}>
                  <DateField
                    label={t("athletes.birthDate")}
                    maxToday
                    dayMonthYear
                    value={form.birth_date}
                    onChange={(value) => updateForm({ birth_date: value })}
                  />
                  <SelectField
                    label={t("athletes.fitnessLevel")}
                    value={form.fitness_level}
                    onChange={(value) => updateForm({ fitness_level: value })}
                    options={[
                      { value: "", label: t("common.none") },
                      {
                        value: "beginner",
                        label: t("athletes.levelBeginner"),
                      },
                      {
                        value: "intermediate",
                        label: t("athletes.levelIntermediate"),
                      },
                      {
                        value: "advanced",
                        label: t("athletes.levelAdvanced"),
                      },
                    ]}
                  />
                </div>
              </>
            ) : (
              <div className="m3-readonly-grid">
                <ReadOnlyField
                  label={t("athletes.fullName")}
                  value={athlete.profile.full_name ?? notRecorded}
                />
                <ReadOnlyField
                  label={t("athletes.phone")}
                  value={
                    athlete.profile.phone ? (
                      <span dir="ltr">{athlete.profile.phone}</span>
                    ) : (
                      notRecorded
                    )
                  }
                />
                <ReadOnlyField
                  label={t("athletes.birthDate")}
                  value={
                    athlete.profile.birth_date
                      ? formatDate(athlete.profile.birth_date)
                      : notRecorded
                  }
                />
                <ReadOnlyField
                  label={t("athletes.fitnessLevel")}
                  value={fitnessLevelLabel(athlete.profile.fitness_level)}
                />
              </div>
            )}
          </Card>

          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">
                  {t("athletes.measurements")}
                </h2>
                <p className="m3-section__subtitle">
                  {t("athletes.measurementsUpdated")}:{" "}
                  {formatDateTime(athlete.profile.updated_at)}
                </p>
              </div>
            </div>
            {editingProfile ? (
              <div className="grid-3">
                {[
                  ["height_cm", t("athletes.height"), t("common.units.cm")],
                  ["weight_kg", t("athletes.weight"), t("common.units.kg")],
                  ["chest_cm", t("athletes.chest"), t("common.units.cm")],
                  ["waist_cm", t("athletes.waist"), t("common.units.cm")],
                  ["hips_cm", t("athletes.hips"), t("common.units.cm")],
                  ["arm_cm", t("athletes.arm"), t("common.units.cm")],
                  ["thigh_cm", t("athletes.thigh"), t("common.units.cm")],
                ].map(([key, label, unit]) => (
                  <TextField
                    key={key}
                    label={label}
                    suffix={unit}
                    inputMode="decimal"
                    value={form[key as keyof typeof form] as string}
                    onChange={(event) =>
                      updateForm({ [key]: event.target.value })
                    }
                  />
                ))}
              </div>
            ) : (
              <div className="m3-readonly-grid m3-readonly-grid--three">
                {measurementFields.map((field) => (
                  <ReadOnlyField
                    key={field.label}
                    label={field.label}
                    value={
                      field.value == null
                        ? notRecorded
                        : `${formatNumber(field.value)} ${field.unit}`
                    }
                  />
                ))}
              </div>
            )}
          </Card>

          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("athletes.training")}</h2>
                <p className="m3-section__subtitle">{t("athletes.subtitle")}</p>
              </div>
            </div>
            {editingProfile ? (
              <>
                <div className="grid-2">
                  <TextField
                    label={t("athletes.goal")}
                    value={form.training_goal}
                    onChange={(event) =>
                      updateForm({ training_goal: event.target.value })
                    }
                  />
                  <TextField
                    label={t("athletes.equipment")}
                    value={form.equipment}
                    onChange={(event) =>
                      updateForm({ equipment: event.target.value })
                    }
                  />
                </div>
                <div className="grid-2" style={{ marginTop: 14 }}>
                  <TextField
                    label={t("athletes.trainingDays")}
                    type="number"
                    min={1}
                    max={7}
                    step={1}
                    inputMode="numeric"
                    value={form.training_days_count}
                    onChange={(event) => {
                      const value = event.target.value
                      if (value === "" || /^[1-7]$/.test(value)) {
                        updateForm({ training_days_count: value })
                      }
                    }}
                  />
                </div>
                <div className="grid-2" style={{ marginTop: 14 }}>
                  <TextField
                    label={t("athletes.sportsHistory")}
                    value={form.sports_history}
                    onChange={(event) =>
                      updateForm({ sports_history: event.target.value })
                    }
                    multiline
                    rows={3}
                  />
                  <TextField
                    label={t("athletes.limitations")}
                    value={form.limitations}
                    onChange={(event) =>
                      updateForm({ limitations: event.target.value })
                    }
                    multiline
                    rows={3}
                  />
                </div>
              </>
            ) : (
              <div className="m3-readonly-grid">
                <ReadOnlyField
                  label={t("athletes.goal")}
                  value={athlete.profile.training_goal ?? notRecorded}
                />
                <ReadOnlyField
                  label={t("athletes.equipment")}
                  value={athlete.profile.equipment ?? notRecorded}
                />
                <ReadOnlyField
                  label={t("athletes.trainingDays")}
                  value={
                    athlete.profile.training_days_count == null
                      ? notRecorded
                      : t("athletes.trainingDaysValue", {
                          count: formatNumber(
                            athlete.profile.training_days_count,
                          ),
                        })
                  }
                />
                <ReadOnlyField
                  label={t("athletes.sportsHistory")}
                  value={athlete.profile.sports_history ?? notRecorded}
                  wide
                />
                <ReadOnlyField
                  label={t("athletes.limitations")}
                  value={athlete.profile.limitations ?? notRecorded}
                  wide
                />
              </div>
            )}
          </Card>

          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">
                  {t("athletes.internalNote")}
                </h2>
                <p className="m3-section__subtitle">
                  {t("athletes.internalNoteHint")}
                </p>
              </div>
              <ShieldAlert size={21} className="muted" />
            </div>
            {editingProfile ? (
              <TextField
                label={t("athletes.internalNote")}
                value={form.internal_coach_note}
                onChange={(event) =>
                  updateForm({ internal_coach_note: event.target.value })
                }
                multiline
                rows={4}
                helper={t("athletes.internalNoteHint")}
              />
            ) : athlete.internal_coach_note ? (
              <p className="m3-profile-note">{athlete.internal_coach_note}</p>
            ) : (
              <p className="muted">{t("person.note.empty")}</p>
            )}
          </Card>

          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">
                  {t("athletes.assignmentHistory")}
                </h2>
                <p className="m3-section__subtitle">{t("athletes.coach")}</p>
              </div>
              <History size={21} className="muted" />
            </div>
            <div className="stack-sm">
              {athlete.assignments.map((assignment) => (
                <div key={assignment.id} className="m3-file-row">
                  <UserRound size={17} className="muted" />
                  <span className="m3-file-row__name">
                    {assignment.coach_name ?? "—"}
                  </span>
                  <span className="muted">
                    {formatDate(assignment.started_at)} —{" "}
                    {assignment.ended_at
                      ? formatDate(assignment.ended_at)
                      : t("status.active")}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ) : null}

      {tab === "programs" ? (
        <div
          className="stack"
          role="tabpanel"
          id="athlete-record-panel-programs"
          aria-labelledby="athlete-record-tab-programs"
        >
          <div className="row row--between">
            <div>
              <h2>{t("athletes.programs")}</h2>
              <p className="muted" style={{ fontSize: 12 }}>
                {t("program.versionHistory")}
              </p>
            </div>
          </div>
          {programsQuery.isLoading ? (
            <Spinner label={t("common.loading")} />
          ) : programsQuery.data?.length ? (
            <div className="stack-sm">
              {programsQuery.data.map((version) => (
                <ProgramReviewCard
                  key={version.id}
                  version={version}
                  defaultOpen={version.status === "ACTIVE"}
                  canEdit={canEdit}
                  onEdit={() =>
                    navigate({
                      to: "/gyms/$gymId/programs/$versionId/edit",
                      params: {
                        gymId: activeGymId!,
                        versionId: version.id,
                      },
                    })
                  }
                  onPrint={() =>
                    window.open(
                      `/print/${version.id}?gym=${activeGymId}`,
                      "_blank",
                    )
                  }
                  onDelete={() => setDeleteTarget(version)}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<ClipboardList size={26} />}
              title={t("athletes.noPrograms")}
              description={t("athletes.noProgramsHint")}
            />
          )}
        </div>
      ) : null}

      {tab === "bodyFiles" ? (
        <div
          role="tabpanel"
          id="athlete-record-panel-bodyFiles"
          aria-labelledby="athlete-record-tab-bodyFiles"
        >
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("athletes.bodyFiles")}</h2>
                <p className="m3-section__subtitle">
                  {t("athletes.filePrivacy")}
                </p>
              </div>
            </div>
            <div className="m3-upload">
              <p
                id={`${uploadId}-hint`}
                className="muted"
                style={{ fontSize: 12 }}
              >
                {t("athletes.uploadHint")}
              </p>
              <label className="m3-field__label" htmlFor={uploadId}>
                {t("athletes.uploadBodyFile")}
              </label>
              <div className="m3-upload__row">
                <input
                  ref={fileInput}
                  id={uploadId}
                  aria-describedby={`${uploadId}-hint`}
                  disabled={uploading || archived}
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  className="sr-only"
                  aria-label={t("athletes.uploadBodyFile")}
                  onChange={(event) => {
                    const file = event.target.files?.[0]
                    if (file) void uploadFile(file)
                  }}
                />
                <Button
                  variant="outlined"
                  icon={<FileUp size={16} />}
                  loading={uploading}
                  disabled={archived}
                  onClick={() => fileInput.current?.click()}
                >
                  {uploading
                    ? t("common.uploading")
                    : t("athletes.uploadBodyFile")}
                </Button>
              </div>
            </div>
            <div style={{ height: 14 }} />
            {athlete.body_files.length === 0 ? (
              <EmptyState
                icon={<FileUp size={24} />}
                title={t("athletes.noBodyFiles")}
              />
            ) : (
              <div className="stack-sm">
                {athlete.body_files.map((file) => (
                  <div key={file.id} className="m3-file-row">
                    <FileUp size={17} className="muted" />
                    <span className="m3-file-row__name">
                      {file.original_name}
                    </span>
                    <span className="muted">
                      {formatBytes(file.size_bytes)} ·{" "}
                      {formatDate(file.created_at)}
                    </span>
                    <Button
                      variant="text"
                      size="sm"
                      icon={<Download size={14} />}
                      onClick={() => downloadFile(file.id, file.original_name)}
                    >
                      {t("common.download")}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      ) : null}

      <Dialog
        open={reassignOpen}
        title={t("athletes.reassignTitle")}
        description={t("athletes.reassignWarning")}
        onClose={() => setReassignOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setReassignOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              onClick={reassignCoach}
              loading={saving}
              disabled={!newCoachId}
            >
              {t("athletes.reassign")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <div className="row">
            <span className="muted">{t("athletes.currentCoach")}:</span>
            <strong>{athlete.coach_name ?? t("athletes.noCoach")}</strong>
          </div>
          <AsyncPickerField
            label={t("athletes.newCoach")}
            value={newCoachId}
            onChange={(value) => setNewCoachId(value)}
            picker={coachPicker}
            getOption={(coach) => ({
              value: coach.user_id,
              label: coach.full_name ?? coach.email,
            })}
            filterOption={(coach) => coach.user_id !== athlete.coach_user_id}
            placeholder={t("common.choose")}
            required
          />
        </div>
      </Dialog>

      <DeleteAthletesDialog
        open={deleteOpen}
        athletes={[
          {
            user_id: athleteId,
            email: athlete.profile.email,
            full_name: athlete.profile.full_name,
          },
        ]}
        onClose={() => setDeleteOpen(false)}
        onDeleted={() =>
          navigate({
            to: athlete.profile.is_archived
              ? "/athletes/archived"
              : "/athletes",
          })
        }
      />

      <ConfirmDialog
        open={archiveOpen}
        title={t("athletes.archiveTitle")}
        description={t("athletes.archiveWarning")}
        confirmLabel={t("athletes.archive")}
        cancelLabel={t("common.cancel")}
        onConfirm={archiveAthlete}
        onClose={() => setArchiveOpen(false)}
        destructive
        loading={saving}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={t("program.deleteTitle")}
        description={`${deleteTarget?.title ?? ""} · ${t(
          "program.versionLabel",
          {
            version: formatNumber(deleteTarget?.version_number ?? 0),
          },
        )} — ${t("program.deleteWarning")}`}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        onConfirm={deleteProgramVersion}
        onClose={() => setDeleteTarget(null)}
        destructive
        loading={saving}
      />

      <Dialog
        open={programOpen}
        title={t("program.newTitle")}
        onClose={() => setProgramOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setProgramOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={createProgram} loading={saving}>
              {t("common.create")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <div className="program-create-intro">
            <span aria-hidden>
              <Sparkles size={18} />
            </span>
            <p>{t("program.createHint")}</p>
          </div>
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <TextField
            label={t("program.titleLabel")}
            value={programTitle}
            onChange={(event) => setProgramTitle(event.target.value)}
            required
          />
          <TextField
            label={t("program.goal")}
            value={programGoal}
            onChange={(event) => setProgramGoal(event.target.value)}
          />
          <div className="grid-2">
            <DateField
              label={t("program.startDate")}
              value={programStart}
              maxValue={programEnd}
              onChange={setProgramStart}
            />
            <DateField
              label={t("program.endDate")}
              value={programEnd}
              minValue={programStart}
              onChange={setProgramEnd}
            />
          </div>
          <div className="row">
            <CalendarDays size={16} className="muted" />
            <span className="muted" style={{ fontSize: 12 }}>
              {t("athletes.coach")}: {athlete.coach_name ?? "—"}
            </span>
          </div>
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
