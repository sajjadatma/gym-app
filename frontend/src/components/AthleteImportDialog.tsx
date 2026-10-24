import { useQueryClient } from "@tanstack/react-query"
import {
  AlertTriangle,
  Check,
  Download,
  FileSpreadsheet,
  FileText,
  Info,
  Upload,
  X,
} from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"
import { translateApiError } from "@/api"
import {
  type AthleteImportPreview,
  type AthleteImportPreviewRow,
  type AthleteImportResult,
  AthletesService,
  type CoachPublic,
} from "@/client"
import { client } from "@/client/client.gen"
import {
  Button,
  Dialog,
  SearchableSelectField,
  SelectField,
  TextField,
} from "@/components/M3"
import { type TranslationKey, useI18n } from "@/i18n"

const MAX_FILE_BYTES = 5 * 1024 * 1024
const ALLOWED_EXTENSIONS = [".csv", ".xlsx"] as const

type Step = "upload" | "preview" | "result"

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function messageText(code: string, t: (key: TranslationKey) => string): string {
  const key = `import.message.${code}` as TranslationKey
  const translated = t(key)
  return translated === key ? code : translated
}

function rowStatusLabel(
  row: AthleteImportPreviewRow,
  t: (key: TranslationKey) => string,
) {
  if (row.status === "valid") return t("athletes.importValid")
  if (row.status === "skip") return t("athletes.importSkipped")
  return t("athletes.importError")
}

export function AthleteImportDialog({
  open,
  onClose,
  onImported,
  coaches,
}: {
  open: boolean
  onClose: () => void
  onImported: () => void
  coaches: CoachPublic[]
}) {
  const { t, formatNumber } = useI18n()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const coachesRef = useRef(coaches)
  coachesRef.current = coaches
  const fileId = useId()
  const [step, setStep] = useState<Step>("upload")
  const [file, setFile] = useState<File | null>(null)
  const [coachId, setCoachId] = useState("")
  const [activationMethod, setActivationMethod] = useState<
    "invite" | "password"
  >("invite")
  const [initialPassword, setInitialPassword] = useState("")
  const [preview, setPreview] = useState<AthleteImportPreview | null>(null)
  const [result, setResult] = useState<AthleteImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [downloading, setDownloading] = useState<"csv" | "xlsx" | null>(null)

  const coachOptions = [
    { value: "", label: t("athletes.importNoDefaultCoach") },
    ...coaches.map((coach) => ({
      value: coach.user_id,
      label: coach.full_name ?? coach.email,
    })),
  ]
  const coachLabel =
    coachOptions.find((option) => option.value === coachId)?.label ??
    t("athletes.importNoDefaultCoach")

  useEffect(() => {
    if (!open) return
    const coachList = coachesRef.current
    setStep("upload")
    setFile(null)
    setCoachId(coachList.length === 1 ? coachList[0].user_id : "")
    setActivationMethod("invite")
    setInitialPassword("")
    setPreview(null)
    setResult(null)
    setError(null)
    setBusy(false)
    setDragging(false)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }, [open])

  function reset() {
    setStep("upload")
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  function pickFile(next: File | null) {
    setError(null)
    setPreview(null)
    setResult(null)
    setStep("upload")
    if (!next) {
      setFile(null)
      return
    }
    const extension = next.name.slice(next.name.lastIndexOf(".")).toLowerCase()
    if (
      !ALLOWED_EXTENSIONS.includes(
        extension as (typeof ALLOWED_EXTENSIONS)[number],
      )
    ) {
      setFile(null)
      setError(t("errors.invalid_file_type"))
      return
    }
    if (next.size > MAX_FILE_BYTES) {
      setFile(null)
      setError(t("errors.file_too_large"))
      return
    }
    setFile(next)
  }

  function handleCoachChange(value: string) {
    setCoachId(value)
    if (preview) {
      setPreview(null)
      setStep("upload")
    }
  }

  async function downloadTemplate(format: "csv" | "xlsx") {
    setDownloading(format)
    setError(null)
    try {
      const response = await client.instance.get(
        "/api/v1/athletes/import/template",
        {
          params: { file_format: format },
          responseType: "blob",
        },
      )
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `athlete-import-template.${format}`
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setDownloading(null)
    }
  }

  async function runPreview(coachOverride?: string) {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const response = await AthletesService.previewAthleteImport({
        body: {
          file,
          default_coach_user_id: (coachOverride ?? coachId) || null,
        },
      })
      setPreview(response.data)
      setStep("preview")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  async function recoverWithCoach(value: string) {
    setCoachId(value)
    if (!value || !file) return
    await runPreview(value)
  }

  function downloadFailureReport() {
    if (!result?.failed?.length) return
    const rows = [
      ["row", "email", "message"],
      ...result.failed.flatMap((failure) =>
        (failure.messages ?? []).map((message) => [
          failure.row_number,
          failure.email,
          messageText(message, t),
        ]),
      ),
    ]
    const csv = rows
      .map((row) =>
        row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(","),
      )
      .join("\n")
    const url = URL.createObjectURL(
      new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" }),
    )
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "athlete-import-errors.csv"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function runImport() {
    if (!file) return
    if (activationMethod === "password" && initialPassword.length < 8) {
      setError(t("errors.initial_password_required"))
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = await AthletesService.bulkImportAthletes({
        body: {
          file,
          default_coach_user_id: coachId || null,
          activation_method: activationMethod,
          initial_password:
            activationMethod === "password" ? initialPassword : null,
        },
      })
      setResult(response.data)
      setStep("result")
      onImported()
      await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setBusy(false)
    }
  }

  const needsCoach =
    preview?.rows.some((row) =>
      (row.messages ?? []).includes("coach_required"),
    ) ?? false

  const footer =
    step === "result" ? (
      <>
        <Button variant="text" onClick={reset}>
          {t("athletes.importAnother")}
        </Button>
        <Button onClick={onClose}>{t("athletes.importDone")}</Button>
      </>
    ) : step === "preview" ? (
      <>
        <Button
          variant="text"
          onClick={() => setStep("upload")}
          disabled={busy}
        >
          {t("common.back")}
        </Button>
        <Button
          onClick={runImport}
          loading={busy}
          disabled={
            busy ||
            !preview ||
            preview.valid === 0 ||
            (activationMethod === "password" && initialPassword.length < 8)
          }
        >
          {t("athletes.confirmImport", {
            count: formatNumber(preview?.valid ?? 0),
          })}
        </Button>
      </>
    ) : (
      <>
        <Button variant="text" onClick={onClose} disabled={busy}>
          {t("common.cancel")}
        </Button>
        <Button
          icon={<Upload size={16} />}
          onClick={() => void runPreview()}
          loading={busy}
          disabled={!file}
        >
          {t("athletes.previewImport")}
        </Button>
      </>
    )

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("athletes.bulkImportTitle")}
      description={t("athletes.bulkImportDescription")}
      size="lg"
      footer={footer}
    >
      <div className="m3-import">
        {error ? (
          <div className="m3-inline-alert" role="alert">
            {error}
          </div>
        ) : null}

        {step === "upload" ? (
          <>
            <section className="m3-import-section">
              <div className="m3-import-section__head">
                <div>
                  <h3>{t("athletes.importTemplate")}</h3>
                  <p className="muted">{t("athletes.importTemplateHint")}</p>
                </div>
                <div className="m3-import-template-actions">
                  <Button
                    variant="outlined"
                    size="sm"
                    icon={<FileText size={15} />}
                    loading={downloading === "csv"}
                    onClick={() => void downloadTemplate("csv")}
                  >
                    {t("athletes.downloadCsv")}
                  </Button>
                  <Button
                    variant="outlined"
                    size="sm"
                    icon={<FileSpreadsheet size={15} />}
                    loading={downloading === "xlsx"}
                    onClick={() => void downloadTemplate("xlsx")}
                  >
                    {t("athletes.downloadXlsx")}
                  </Button>
                </div>
              </div>
              <details className="m3-import-guide">
                <summary>{t("athletes.importColumns")}</summary>
                <p>
                  <strong>{t("auth.email")} *</strong>
                  {" · "}
                  {t("athletes.fullName")}
                  {" · "}
                  {t("athletes.phone")}
                  {" · "}
                  {t("athletes.coach")}
                  {" · "}
                  {t("athletes.goal")}
                  {" · "}
                  {t("athletes.height")} (cm)
                  {" · "}
                  {t("athletes.weight")} (kg)
                  {" · "}
                  {t("athletes.trainingDays")} (1–7)
                </p>
                <p className="muted">{t("athletes.importTemplateNote")}</p>
              </details>
            </section>

            <section className="m3-import-section">
              <h3>{t("athletes.importFile")}</h3>
              <fieldset
                className={`m3-import-dropzone ${dragging ? "is-dragging" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault()
                  setDragging(true)
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault()
                  setDragging(false)
                  pickFile(event.dataTransfer.files[0] ?? null)
                }}
              >
                <legend className="sr-only">{t("athletes.importFile")}</legend>
                <input
                  ref={fileInputRef}
                  id={fileId}
                  type="file"
                  accept=".csv,.xlsx"
                  className="sr-only"
                  onChange={(event) =>
                    pickFile(event.target.files?.[0] ?? null)
                  }
                />
                <Upload size={26} aria-hidden className="muted" />
                <p>{t("athletes.importDropHint")}</p>
                <Button
                  variant="outlined"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                >
                  {t("athletes.importChooseFile")}
                </Button>
                <span className="muted m3-import-dropzone__hint">
                  {t("athletes.importFileHint")}
                </span>
              </fieldset>
              {file ? (
                <div className="m3-import-file">
                  <FileText size={18} aria-hidden />
                  <span className="m3-import-file__name">{file.name}</span>
                  <span className="muted">{formatBytes(file.size)}</span>
                  <button
                    type="button"
                    className="m3-search-clear"
                    aria-label={t("athletes.importRemoveFile")}
                    onClick={() => pickFile(null)}
                  >
                    <X size={15} aria-hidden />
                  </button>
                </div>
              ) : null}
            </section>

            <section className="m3-import-section">
              <h3>{t("athletes.importSettings")}</h3>
              <div className="grid-2">
                <SearchableSelectField
                  label={t("athletes.importDefaultCoach")}
                  value={coachId}
                  onChange={handleCoachChange}
                  options={coachOptions}
                  placeholder={t("athletes.importNoDefaultCoach")}
                  helper={t("athletes.importDefaultCoachHint")}
                />
                <SelectField
                  label={t("gyms.activationMethod")}
                  value={activationMethod}
                  onChange={(value) =>
                    setActivationMethod(value as "invite" | "password")
                  }
                  options={[
                    { value: "invite", label: t("gyms.methodInvite") },
                    { value: "password", label: t("gyms.methodPassword") },
                  ]}
                  helper={t("athletes.importActivationHint")}
                />
              </div>
              {activationMethod === "password" ? (
                <TextField
                  label={t("gyms.initialPassword")}
                  type="password"
                  dir="ltr"
                  value={initialPassword}
                  onChange={(event) => setInitialPassword(event.target.value)}
                  helper={t("gyms.initialPasswordHint")}
                  required
                />
              ) : null}
            </section>
          </>
        ) : null}

        {step === "preview" && preview ? (
          <section className="m3-import-section">
            {needsCoach ? (
              <div className="m3-import-fix" role="alert">
                <div>
                  <strong>{t("athletes.importCoachRequiredTitle")}</strong>
                  <p>{t("athletes.importCoachRequiredHint")}</p>
                </div>
                <SearchableSelectField
                  label={t("athletes.importDefaultCoach")}
                  value={coachId}
                  onChange={(value) => void recoverWithCoach(value)}
                  options={coachOptions}
                  placeholder={t("athletes.chooseCoach")}
                  disabled={busy}
                />
              </div>
            ) : null}
            <p className="m3-import-context">
              <span>
                {t("athletes.importFile")}: <strong>{file?.name}</strong>
              </span>
              <span>
                {t("athletes.importDefaultCoach")}:{" "}
                <strong>{coachLabel}</strong>
              </span>
              <span>
                {t("gyms.activationMethod")}:{" "}
                <strong>
                  {activationMethod === "invite"
                    ? t("gyms.methodInvite")
                    : t("gyms.methodPassword")}
                </strong>
              </span>
            </p>
            <div className="m3-import-summary" aria-live="polite">
              <span className="m3-import-chip is-valid">
                <Check size={14} aria-hidden />
                {t("athletes.importValid")}: {formatNumber(preview.valid)}
              </span>
              <span className="m3-import-chip is-skip">
                <Info size={14} aria-hidden />
                {t("athletes.importSkipped")}: {formatNumber(preview.skipped)}
              </span>
              <span className="m3-import-chip is-error">
                <AlertTriangle size={14} aria-hidden />
                {t("athletes.importError")}: {formatNumber(preview.errors)}
              </span>
              <span className="muted">
                {t("athletes.importTotal", {
                  count: formatNumber(preview.total),
                })}
              </span>
            </div>
            <div className="m3-table-wrap m3-import-table-wrap">
              <table className="m3-table m3-import-table">
                <thead>
                  <tr>
                    <th scope="col">{t("athletes.importRow")}</th>
                    <th scope="col">{t("athletes.importAthlete")}</th>
                    <th scope="col">{t("athletes.importCoach")}</th>
                    <th scope="col">{t("athletes.importStatus")}</th>
                    <th scope="col">{t("athletes.importMessage")}</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row) => (
                    <tr key={row.row_number} className={`is-${row.status}`}>
                      <td className="m3-import-table__row">
                        {formatNumber(row.row_number)}
                      </td>
                      <td>
                        <strong>{row.full_name ?? "—"}</strong>
                        <div dir="ltr" className="muted">
                          {row.email || "—"}
                        </div>
                      </td>
                      <td>{row.coach_name ?? row.coach_email ?? "—"}</td>
                      <td>
                        <span className={`m3-import-pill is-${row.status}`}>
                          {rowStatusLabel(row, t)}
                        </span>
                      </td>
                      <td>
                        {(row.messages ?? []).length ? (
                          <ul className="m3-import-messages">
                            {(row.messages ?? []).map((message) => (
                              <li key={message}>{messageText(message, t)}</li>
                            ))}
                          </ul>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview.valid === 0 && !needsCoach ? (
              <div className="m3-inline-alert" role="alert">
                {t("athletes.importNoValidRows")}
              </div>
            ) : null}
          </section>
        ) : null}

        {step === "result" && result ? (
          <section className="m3-import-section">
            <div className="m3-import-result">
              <div className="m3-import-result__icon" aria-hidden>
                <Check size={22} />
              </div>
              <div>
                <h3>{t("athletes.importResultTitle")}</h3>
                <p className="muted">
                  {t("athletes.importResultSummary", {
                    created: formatNumber(result.created),
                    skipped: formatNumber(result.skipped),
                    failed: formatNumber((result.failed ?? []).length),
                  })}
                </p>
              </div>
            </div>
            {(result.failed ?? []).length ? (
              <div className="m3-table-wrap m3-import-table-wrap">
                <table className="m3-table m3-import-table">
                  <thead>
                    <tr>
                      <th scope="col">{t("athletes.importRow")}</th>
                      <th scope="col">{t("auth.email")}</th>
                      <th scope="col">{t("athletes.importMessage")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(result.failed ?? []).map((failure) => (
                      <tr key={`${failure.row_number}-${failure.email}`}>
                        <td className="m3-import-table__row">
                          {formatNumber(failure.row_number)}
                        </td>
                        <td dir="ltr">{failure.email || "—"}</td>
                        <td>
                          <ul className="m3-import-messages">
                            {(failure.messages ?? []).map((message) => (
                              <li key={message}>{messageText(message, t)}</li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {result.failed?.length ? (
              <Button
                variant="outlined"
                size="sm"
                icon={<Download size={15} />}
                onClick={downloadFailureReport}
              >
                {t("athletes.importDownloadErrors")}
              </Button>
            ) : null}
            <p className="muted m3-import-result__hint">
              {t("athletes.importResultHint")}{" "}
              {activationMethod === "password"
                ? t("athletes.importResultPasswordHint")
                : t("athletes.importResultInviteHint")}
            </p>
            {result.failed?.length ? (
              <p className="muted m3-import-result__hint">
                {t("athletes.importResultFailedHint")}
              </p>
            ) : null}
          </section>
        ) : null}
      </div>
    </Dialog>
  )
}
