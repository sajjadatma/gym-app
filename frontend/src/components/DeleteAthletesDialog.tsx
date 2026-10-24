import { useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"
import { AthletesService } from "@/client"
import { Button, Dialog, TextField } from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export type DeleteAthleteTarget = {
  user_id: string
  email: string
  full_name?: string | null
}

export function DeleteAthletesDialog({
  open,
  athletes,
  onClose,
  onDeleted,
}: {
  open: boolean
  athletes: DeleteAthleteTarget[]
  onClose: () => void
  onDeleted: () => void
}) {
  const { t, formatNumber } = useI18n()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [confirmation, setConfirmation] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const single = athletes.length === 1
  const expected = single
    ? (athletes[0]?.email ?? "")
    : t("athletes.deleteConfirmWord")
  const matches = single
    ? confirmation.trim().toLowerCase() === expected.toLowerCase()
    : confirmation.trim() === expected

  useEffect(() => {
    if (!open) return
    setConfirmation("")
    setError(null)
    setBusy(false)
  }, [open])

  async function confirmDelete() {
    if (!matches || busy) return
    setBusy(true)
    setError(null)
    let deleted = 0
    let failed = 0
    for (const athlete of athletes) {
      try {
        await AthletesService.deleteAthlete({
          path: { athlete_user_id: athlete.user_id },
        })
        deleted += 1
      } catch {
        failed += 1
      }
    }
    await queryClient.invalidateQueries({ queryKey: ["athletes"] })
    await queryClient.invalidateQueries({ queryKey: ["athlete"] })
    await queryClient.invalidateQueries({ queryKey: ["programs"] })
    await queryClient.invalidateQueries({ queryKey: ["program-version"] })
    setBusy(false)
    if (failed) {
      setError(
        t("athletes.deleteSummary", {
          deleted: formatNumber(deleted),
          failed: formatNumber(failed),
        }),
      )
      return
    }
    show(t("athletes.deleted"), "success")
    onDeleted()
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="sm"
      title={
        single
          ? t("athletes.deleteTitle")
          : t("athletes.deleteTitleMultiple", {
              count: formatNumber(athletes.length),
            })
      }
      footer={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="danger"
            icon={<Trash2 size={16} />}
            onClick={() => void confirmDelete()}
            loading={busy}
            disabled={!matches}
          >
            {t("athletes.deletePermanently")}
          </Button>
        </>
      }
    >
      <div className="stack">
        <div className="m3-delete-warning">
          <AlertTriangle size={20} aria-hidden />
          <p>{t("athletes.deleteWarning")}</p>
        </div>
        <div className="m3-delete-targets">
          {athletes.slice(0, 5).map((athlete) => (
            <div key={athlete.user_id}>
              <strong>{athlete.full_name ?? athlete.email}</strong>
              {athlete.full_name ? (
                <span className="muted" dir="ltr">
                  {athlete.email}
                </span>
              ) : null}
            </div>
          ))}
          {athletes.length > 5 ? (
            <span className="muted">+{formatNumber(athletes.length - 5)}</span>
          ) : null}
        </div>
        <TextField
          label={
            single
              ? t("athletes.deleteTypeEmail", { email: expected })
              : t("athletes.deleteTypeWord", { word: expected })
          }
          value={confirmation}
          onChange={(event) => setConfirmation(event.target.value)}
          dir={single ? "ltr" : undefined}
          autoComplete="off"
          required
        />
        {error ? (
          <div className="m3-inline-alert" role="alert">
            {error}
          </div>
        ) : null}
      </div>
    </Dialog>
  )
}
