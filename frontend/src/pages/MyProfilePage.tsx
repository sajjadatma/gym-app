import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Download, FileUp, Mail, Save, UserRound } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { AthletesService } from "@/client"
import { client } from "@/client/client.gen"
import { DateField } from "@/components/DateField"
import {
  Avatar,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { formatBytes } from "@/lib/format"
import { useSnackbar } from "@/snackbar"

export function MyProfilePage() {
  const { t, formatDate, formatDateTime } = useI18n()
  const { activeGym, activeGymId, activeRole } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { show } = useSnackbar()
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const hydratedProfileRef = useRef<string | null>(null)
  const uploadId = useId()
  const [form, setForm] = useState({
    phone: "",
    birth_date: null as string | null,
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
  })

  const profileQuery = useQuery({
    queryKey: ["athlete-me", activeGymId],
    queryFn: async () => (await AthletesService.readMyAthleteProfile()).data,
    enabled: Boolean(activeGymId && activeRole === "ATHLETE"),
  })

  const data = profileQuery.data
  useEffect(() => {
    if (!data) return
    const profileKey = `${activeGymId}:${data.profile.user_id}`
    if (hydratedProfileRef.current === profileKey) return
    hydratedProfileRef.current = profileKey
    setForm({
      phone: data.profile.phone ?? "",
      birth_date: data.profile.birth_date ?? null,
      height_cm: data.profile.height_cm?.toString() ?? "",
      weight_kg: data.profile.weight_kg?.toString() ?? "",
      chest_cm: data.profile.chest_cm?.toString() ?? "",
      waist_cm: data.profile.waist_cm?.toString() ?? "",
      hips_cm: data.profile.hips_cm?.toString() ?? "",
      arm_cm: data.profile.arm_cm?.toString() ?? "",
      thigh_cm: data.profile.thigh_cm?.toString() ?? "",
      training_goal: data.profile.training_goal ?? "",
      sports_history: data.profile.sports_history ?? "",
      fitness_level: data.profile.fitness_level ?? "",
      limitations: data.profile.limitations ?? "",
      training_days_count: data.profile.training_days_count?.toString() ?? "",
    })
  }, [activeGymId, data])

  if (!activeGym) {
    return (
      <PageHeader
        title={t("my.profileTitle")}
        subtitle={t("context.noGymHint")}
      />
    )
  }
  if (activeRole !== "ATHLETE") {
    return <ErrorState message={t("errors.athlete_staff_access_required")} />
  }
  if (profileQuery.isLoading) return <Spinner label={t("common.loading")} />
  if (profileQuery.isError || !data) {
    return (
      <ErrorState
        message={translateApiError(profileQuery.error, t)}
        onRetry={() => profileQuery.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  const current = data

  function convert(value: string) {
    return value.trim() ? Number(value) : null
  }

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const response = await AthletesService.updateMyAthleteProfile({
        body: {
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
        },
      })
      queryClient.setQueryData(["athlete-me", activeGymId], response.data)
      show(t("my.saved"), "success")
      await navigate({
        to: "/gyms/$gymId",
        params: { gymId: activeGymId! },
      })
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
        path: { athlete_user_id: current.profile.user_id },
        body: { file },
      })
      await queryClient.invalidateQueries({
        queryKey: ["athlete-me", activeGymId],
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
        `/api/v1/athletes/${current.profile.user_id}/body-files/${fileId}/download`,
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

  return (
    <>
      <PageHeader
        title={t("my.profileTitle")}
        subtitle={`${activeGym.name} · ${t("my.profileSubtitle")}`}
        actions={
          <Button icon={<Save size={16} />} onClick={save} loading={saving}>
            {t("my.updateProfile")}
          </Button>
        }
      />

      {error ? (
        <div className="m3-inline-alert" style={{ marginBottom: 14 }}>
          {error}
        </div>
      ) : null}

      <div className="grid-2">
        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("my.coach")}</h2>
              <p className="m3-section__subtitle">{t("athletes.coachInfo")}</p>
            </div>
            <UserRound size={22} className="muted" />
          </div>
          {data.coach_name ? (
            <div className="row">
              <Avatar name={data.coach_name} />
              <div>
                <strong>{data.coach_name}</strong>
                <div className="muted" dir="ltr" style={{ fontSize: 11.5 }}>
                  <Mail size={13} style={{ verticalAlign: "middle" }} />{" "}
                  {data.coach_email}
                </div>
              </div>
            </div>
          ) : (
            <p className="muted">{t("athletes.noCoachInfo")}</p>
          )}
        </Card>

        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("athletes.identity")}</h2>
              <p className="m3-section__subtitle">
                {data.profile.full_name} · {data.profile.email}
              </p>
            </div>
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
            <DateField
              label={t("athletes.birthDate")}
              maxToday
              dayMonthYear
              value={form.birth_date}
              onChange={(value) => setForm({ ...form, birth_date: value })}
            />
          </div>
        </Card>
      </div>

      <div style={{ height: 16 }} />

      <Card>
        <div className="m3-section__header">
          <div>
            <h2 className="m3-section__title">{t("my.measurements")}</h2>
            <p className="m3-section__subtitle">
              {t("athletes.measurementsUpdated")}:{" "}
              {formatDateTime(data.profile.updated_at)}
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

      <div style={{ height: 16 }} />

      <Card>
        <div className="m3-section__header">
          <div>
            <h2 className="m3-section__title">{t("athletes.training")}</h2>
            <p className="m3-section__subtitle">{t("my.profileSubtitle")}</p>
          </div>
        </div>
        <div className="grid-2">
          <TextField
            label={t("my.goal")}
            value={form.training_goal}
            onChange={(event) =>
              setForm({ ...form, training_goal: event.target.value })
            }
          />
          <SelectField
            label={t("athletes.fitnessLevel")}
            value={form.fitness_level}
            onChange={(value) => setForm({ ...form, fitness_level: value })}
            options={[
              { value: "", label: t("common.none") },
              { value: "beginner", label: t("athletes.levelBeginner") },
              { value: "intermediate", label: t("athletes.levelIntermediate") },
              { value: "advanced", label: t("athletes.levelAdvanced") },
            ]}
          />
        </div>
        <div className="grid-2 m3-mt-xs">
          <TextField
            label={t("my.trainingDays")}
            type="number"
            min={1}
            max={7}
            step={1}
            inputMode="numeric"
            value={form.training_days_count}
            onChange={(event) => {
              const value = event.target.value
              if (value === "" || /^[1-7]$/.test(value)) {
                setForm({ ...form, training_days_count: value })
              }
            }}
          />
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

      <div style={{ height: 16 }} />

      <Card>
        <div className="m3-section__header">
          <div>
            <h2 className="m3-section__title">{t("my.bodyAnalysis")}</h2>
            <p className="m3-section__subtitle">{t("athletes.filePrivacy")}</p>
          </div>
        </div>
        <div className="m3-upload">
          <p id={`${uploadId}-hint`} className="muted" style={{ fontSize: 12 }}>
            {t("athletes.uploadHint")}
          </p>
          <label className="m3-field__label" htmlFor={uploadId}>
            {t("my.upload")}
          </label>
          <div className="m3-upload__row">
            <input
              ref={fileInput}
              id={uploadId}
              aria-describedby={`${uploadId}-hint`}
              disabled={uploading}
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              className="sr-only"
              aria-label={t("my.upload")}
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
              {uploading ? t("common.uploading") : t("my.upload")}
            </Button>
          </div>
        </div>
        <div style={{ height: 12 }} />
        {data.body_files.length === 0 ? (
          <EmptyState icon={<FileUp size={24} />} title={t("my.noFiles")} />
        ) : (
          <div className="stack-sm">
            {data.body_files.map((file) => (
              <div key={file.id} className="m3-file-row">
                <FileUp size={17} className="muted" />
                <span className="m3-file-row__name">{file.original_name}</span>
                <span className="muted">
                  {formatBytes(file.size_bytes)} · {formatDate(file.created_at)}
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
    </>
  )
}
