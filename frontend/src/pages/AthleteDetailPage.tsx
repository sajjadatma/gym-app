import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  Archive,
  ArrowRight,
  CalendarDays,
  ClipboardList,
  Download,
  FileUp,
  History,
  Mail,
  Phone,
  Plus,
  Printer,
  RefreshCw,
  Save,
  ShieldAlert,
  UserRound,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  AthletesService,
  GymsService,
  ProgramsService,
  type ProgramVersionSummary,
} from "@/client"
import { client } from "@/client/client.gen"
import { DateField } from "@/components/DateField"
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
import { type TranslationKey, useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

const DAYS = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"] as const

type Tab = "profile" | "programs" | "bodyFiles"

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function AthleteDetailPage({ athleteId }: { athleteId: string }) {
  const { t, formatDate, formatDateTime, formatNumber } = useI18n()
  const { activeGym, activeGymId, isAdmin, activeRole, me } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [tab, setTab] = useState<Tab>("profile")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [reassignOpen, setReassignOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [programOpen, setProgramOpen] = useState(false)
  const [newCoachId, setNewCoachId] = useState("")
  const [programTitle, setProgramTitle] = useState("")
  const [programGoal, setProgramGoal] = useState("")
  const [programStart, setProgramStart] = useState<string | null>(null)
  const [programEnd, setProgramEnd] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState({
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
    training_days: [] as string[],
    equipment: "",
    internal_coach_note: "",
  })

  const athleteQuery = useQuery({
    queryKey: ["athlete", activeGymId, athleteId],
    queryFn: async () =>
      (
        await AthletesService.readAthlete({
          path: { athlete_user_id: athleteId },
        })
      ).data,
    enabled: Boolean(activeGymId),
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
  })

  const coachesQuery = useQuery({
    queryKey: ["coaches", activeGymId],
    queryFn: async () =>
      (
        await GymsService.listCoaches({
          path: { gym_id: activeGymId! },
        })
      ).data.data,
    enabled: Boolean(activeGymId && isAdmin),
  })

  const athlete = athleteQuery.data
  useEffect(() => {
    if (!athlete) return
    setForm({
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
      training_days: athlete.profile.training_days ?? [],
      equipment: athlete.profile.equipment ?? "",
      internal_coach_note: athlete.internal_coach_note ?? "",
    })
  }, [athlete])

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

  const canEdit =
    isAdmin || (activeRole === "COACH" && athlete.coach_user_id === me?.id)
  const activeProgram = programsQuery.data?.find(
    (item) => item.status === "ACTIVE",
  )
  const coachOptions = (coachesQuery.data ?? [])
    .filter((coach) => coach.user_id !== athlete.coach_user_id)
    .map((coach) => ({
      value: coach.user_id,
      label: coach.full_name ?? coach.email,
    }))

  function convert(value: string) {
    return value.trim() ? Number(value) : null
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
          training_days: form.training_days,
          equipment: form.equipment || null,
          internal_coach_note: form.internal_coach_note || null,
        },
      })
      queryClient.setQueryData(
        ["athlete", activeGymId, athleteId],
        response.data,
      )
      show(t("athletes.noteSaved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
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
        to: "/programs/$versionId/edit",
        params: { versionId: response.data.id },
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function createDraftFrom(version: ProgramVersionSummary) {
    setSaving(true)
    setError(null)
    try {
      const response = await ProgramsService.createNewDraft({
        path: { version_id: version.id },
      })
      await queryClient.invalidateQueries({
        queryKey: ["programs", activeGymId, athleteId],
      })
      navigate({
        to: "/programs/$versionId/edit",
        params: { versionId: response.data.id },
      })
    } catch (err) {
      show(translateApiError(err, t), "error")
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
        navigate({ to: "/athletes" })
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
      navigate({ to: "/athletes" })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function uploadFile(file: File) {
    if (file.size > 10 * 1024 * 1024) {
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

  function toggleDay(day: string) {
    setForm((current) => ({
      ...current,
      training_days: current.training_days.includes(day)
        ? current.training_days.filter((value) => value !== day)
        : [...current.training_days, day],
    }))
  }

  const tabItems = [
    { value: "profile", label: t("athletes.profile") },
    {
      value: "programs",
      label: t("athletes.programs"),
      count: programsQuery.data?.length ?? 0,
    },
    {
      value: "bodyFiles",
      label: t("athletes.bodyFiles"),
      count: athlete.body_files.length,
    },
  ]

  return (
    <>
      <PageHeader
        title={athlete.profile.full_name ?? athlete.profile.email}
        subtitle={`${activeGym.name} · ${athlete.coach_name ?? t("athletes.noCoach")}`}
        onBack={() => navigate({ to: "/athletes" })}
        backLabel={t("common.back")}
        actions={
          <>
            {isAdmin ? (
              <>
                <Button
                  variant="outlined"
                  icon={<RefreshCw size={16} />}
                  onClick={() => {
                    setError(null)
                    setReassignOpen(true)
                  }}
                >
                  {t("athletes.reassign")}
                </Button>
                <Button
                  variant="outlined"
                  icon={<Archive size={16} />}
                  onClick={() => setArchiveOpen(true)}
                >
                  {t("athletes.archive")}
                </Button>
              </>
            ) : null}
            {canEdit ? (
              <Button
                icon={<Plus size={17} />}
                onClick={() => setProgramOpen(true)}
              >
                {t("athletes.createProgram")}
              </Button>
            ) : null}
          </>
        }
      />

      <Card className="m3-card--outlined">
        <div
          className="row"
          style={{ gap: 16, flexWrap: "nowrap", alignItems: "flex-start" }}
        >
          <Avatar name={athlete.profile.full_name ?? athlete.profile.email} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="row" style={{ gap: 8 }}>
              <strong>
                {athlete.profile.full_name ?? athlete.profile.email}
              </strong>
              <StatusBadge
                status={athlete.profile.is_archived ? "archived" : "active"}
              />
            </div>
            <div className="m3-entity-card__meta" style={{ marginTop: 4 }}>
              <span dir="ltr">
                <Mail size={13} style={{ verticalAlign: "middle" }} />{" "}
                {athlete.profile.email}
              </span>
              {athlete.profile.phone ? (
                <span dir="ltr">
                  <Phone size={13} style={{ verticalAlign: "middle" }} />{" "}
                  {athlete.profile.phone}
                </span>
              ) : null}
              <span>
                <UserRound size={13} style={{ verticalAlign: "middle" }} />{" "}
                {athlete.coach_name ?? t("athletes.noCoach")}
              </span>
            </div>
            {activeProgram ? (
              <div className="row" style={{ marginTop: 10 }}>
                <span className="m3-status m3-status--active">
                  {activeProgram.title} ·{" "}
                  {t("program.versionLabel", {
                    version: formatNumber(activeProgram.version_number),
                  })}
                </span>
                <Button
                  variant="text"
                  size="sm"
                  icon={<ArrowRight size={14} />}
                  onClick={() =>
                    navigate({
                      to: "/programs/$versionId/edit",
                      params: { versionId: activeProgram.id },
                    })
                  }
                >
                  {t("common.open")}
                </Button>
              </div>
            ) : null}
          </div>
        </div>
      </Card>

      <div style={{ height: 18 }} />
      <Tabs
        tabs={tabItems}
        value={tab}
        onChange={(value) => setTab(value as Tab)}
      />

      {error ? (
        <div className="m3-inline-alert" style={{ marginBottom: 14 }}>
          {error}
        </div>
      ) : null}

      {tab === "profile" ? (
        <div className="stack">
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("athletes.identity")}</h2>
                <p className="m3-section__subtitle">
                  {t("athletes.measurementsUpdated")}:{" "}
                  {formatDateTime(athlete.profile.updated_at)}
                </p>
              </div>
              <Avatar
                name={athlete.profile.full_name ?? athlete.profile.email}
              />
            </div>
            <div className="grid-2">
              <TextField
                label={t("athletes.fullName")}
                value={form.full_name}
                onChange={(event) =>
                  setForm({ ...form, full_name: event.target.value })
                }
              />
              <TextField
                label={t("athletes.phone")}
                dir="ltr"
                value={form.phone}
                onChange={(event) =>
                  setForm({ ...form, phone: event.target.value })
                }
              />
            </div>
            <div className="grid-2" style={{ marginTop: 14 }}>
              <DateField
                label={t("athletes.birthDate")}
                value={form.birth_date}
                onChange={(value) => setForm({ ...form, birth_date: value })}
              />
              <SelectField
                label={t("athletes.fitnessLevel")}
                value={form.fitness_level}
                onChange={(value) => setForm({ ...form, fitness_level: value })}
                options={[
                  { value: "", label: t("common.none") },
                  { value: "beginner", label: t("athletes.levelBeginner") },
                  {
                    value: "intermediate",
                    label: t("athletes.levelIntermediate"),
                  },
                  { value: "advanced", label: t("athletes.levelAdvanced") },
                ]}
              />
            </div>
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
                    setForm({ ...form, [key]: event.target.value })
                  }
                />
              ))}
            </div>
          </Card>

          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("athletes.training")}</h2>
                <p className="m3-section__subtitle">{t("athletes.subtitle")}</p>
              </div>
            </div>
            <div className="grid-2">
              <TextField
                label={t("athletes.goal")}
                value={form.training_goal}
                onChange={(event) =>
                  setForm({ ...form, training_goal: event.target.value })
                }
              />
              <TextField
                label={t("athletes.equipment")}
                value={form.equipment}
                onChange={(event) =>
                  setForm({ ...form, equipment: event.target.value })
                }
              />
            </div>
            <div style={{ marginTop: 14 }}>
              <div className="m3-field__label" style={{ marginBottom: 8 }}>
                {t("athletes.trainingDays")}
              </div>
              <div className="row">
                {DAYS.map((day) => (
                  <button
                    key={day}
                    type="button"
                    className={`m3-chip ${form.training_days.includes(day) ? "m3-chip--selected" : ""}`}
                    onClick={() => toggleDay(day)}
                    aria-pressed={form.training_days.includes(day)}
                  >
                    {t(`weekday.${day}` as TranslationKey)}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid-2" style={{ marginTop: 14 }}>
              <TextField
                label={t("athletes.sportsHistory")}
                value={form.sports_history}
                onChange={(event) =>
                  setForm({ ...form, sports_history: event.target.value })
                }
                multiline
                rows={3}
              />
              <TextField
                label={t("athletes.limitations")}
                value={form.limitations}
                onChange={(event) =>
                  setForm({ ...form, limitations: event.target.value })
                }
                multiline
                rows={3}
              />
            </div>
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
            <TextField
              label={t("athletes.internalNote")}
              value={form.internal_coach_note}
              onChange={(event) =>
                setForm({ ...form, internal_coach_note: event.target.value })
              }
              multiline
              rows={4}
              helper={t("athletes.internalNoteHint")}
            />
          </Card>

          <div className="row" style={{ justifyContent: "flex-end" }}>
            <Button
              icon={<Save size={17} />}
              onClick={saveProfile}
              loading={saving}
            >
              {t("common.save")}
            </Button>
          </div>

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
        <div className="stack">
          <div className="row row--between">
            <div>
              <h2>{t("athletes.programs")}</h2>
              <p className="muted" style={{ fontSize: 12 }}>
                {t("program.versionHistory")}
              </p>
            </div>
            {canEdit ? (
              <Button
                icon={<Plus size={17} />}
                onClick={() => setProgramOpen(true)}
              >
                {t("athletes.createProgram")}
              </Button>
            ) : null}
          </div>
          {programsQuery.isLoading ? (
            <Spinner label={t("common.loading")} />
          ) : programsQuery.data?.length ? (
            <div className="stack-sm">
              {programsQuery.data.map((version) => (
                <div key={version.id} className="m3-version-row">
                  <div className="m3-version-row__main">
                    <ClipboardList size={20} className="muted" />
                    <div>
                      <div className="m3-version-row__title">
                        {version.title}{" "}
                        <span className="muted">
                          ·{" "}
                          {t("program.versionLabel", {
                            version: formatNumber(version.version_number),
                          })}
                        </span>
                      </div>
                      <div className="m3-version-row__meta">
                        {t("program.days")}: {formatNumber(version.day_count)} ·{" "}
                        {version.coach_name ?? ""} ·{" "}
                        {formatDate(version.created_at)}
                      </div>
                    </div>
                  </div>
                  <div className="row" style={{ gap: 4 }}>
                    <StatusBadge status={version.status.toLowerCase()} />
                    {version.status === "DRAFT" && canEdit ? (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() =>
                          navigate({
                            to: "/programs/$versionId/edit",
                            params: { versionId: version.id },
                          })
                        }
                      >
                        {t("common.edit")}
                      </Button>
                    ) : (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() =>
                          navigate({
                            to: "/programs/$versionId/edit",
                            params: { versionId: version.id },
                          })
                        }
                      >
                        {t("common.open")}
                      </Button>
                    )}
                    {version.status !== "DRAFT" ? (
                      <Button
                        variant="text"
                        size="sm"
                        icon={<Printer size={14} />}
                        onClick={() =>
                          window.open(`/print/${version.id}`, "_blank")
                        }
                      >
                        {t("common.print")}
                      </Button>
                    ) : null}
                    {canEdit ? (
                      <Button
                        variant="text"
                        size="sm"
                        icon={<RefreshCw size={14} />}
                        disabled={saving}
                        onClick={() => createDraftFrom(version)}
                      >
                        {t("program.newVersion")}
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={<ClipboardList size={26} />}
              title={t("athletes.noPrograms")}
              description={t("athletes.noProgramsHint")}
              action={
                canEdit ? (
                  <Button
                    icon={<Plus size={17} />}
                    onClick={() => setProgramOpen(true)}
                  >
                    {t("athletes.createProgram")}
                  </Button>
                ) : undefined
              }
            />
          )}
        </div>
      ) : null}

      {tab === "bodyFiles" ? (
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
            <p className="muted" style={{ fontSize: 12 }}>
              {t("athletes.uploadHint")}
            </p>
            <div className="m3-upload__row">
              <input
                ref={fileInput}
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
          <SelectField
            label={t("athletes.newCoach")}
            value={newCoachId}
            onChange={setNewCoachId}
            options={coachOptions}
            placeholder={t("common.choose")}
            required
          />
        </div>
      </Dialog>

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
              onChange={setProgramStart}
            />
            <DateField
              label={t("program.endDate")}
              value={programEnd}
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
    </>
  )
}
