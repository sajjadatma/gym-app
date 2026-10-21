import { useNavigate } from "@tanstack/react-router"
import { KeyRound } from "lucide-react"
import { type FormEvent, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { UsersService } from "@/client"
import { AuthLayout } from "@/components/AuthLayout"
import { Button, Spinner, TextField } from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function ChangePasswordPage() {
  const { t } = useI18n()
  const { me, refresh, isLoading } = useAuth()
  const navigate = useNavigate()
  const { show } = useSnackbar()
  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    current?: string
    password?: string
    confirm?: string
  }>({})
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const errors: typeof fieldErrors = {}
    if (!current) errors.current = t("validation.required")
    if (password.length < 8) errors.password = t("validation.minPassword")
    if (confirm !== password) errors.confirm = t("validation.passwordMismatch")
    setFieldErrors(errors)
    if (Object.keys(errors).length) return
    setLoading(true)
    setError(null)
    try {
      await UsersService.updatePasswordMe({
        body: { current_password: current, new_password: password },
      })
      await refresh()
      show(t("auth.passwordChanged"), "success")
      navigate({ to: "/" })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div
        style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}
      >
        <Spinner label={t("common.loading")} />
      </div>
    )
  }

  return (
    <AuthLayout
      title={t("auth.changePasswordTitle")}
      subtitle={t("auth.changePasswordSubtitle")}
      note={me?.must_change_password ? t("auth.changeRequired") : undefined}
    >
      <form className="m3-auth-form" onSubmit={handleSubmit} noValidate>
        {error ? (
          <div className="m3-inline-alert" role="alert">
            {error}
          </div>
        ) : null}
        <TextField
          label={t("auth.currentPassword")}
          type="password"
          dir="ltr"
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
          leading={<KeyRound size={18} />}
          error={fieldErrors.current}
          required
        />
        <TextField
          label={t("auth.newPassword")}
          type="password"
          dir="ltr"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          leading={<KeyRound size={18} />}
          error={fieldErrors.password}
          required
        />
        <TextField
          label={t("auth.confirmPassword")}
          type="password"
          dir="ltr"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          leading={<KeyRound size={18} />}
          error={fieldErrors.confirm}
          required
        />
        <Button type="submit" fullWidth loading={loading}>
          {t("auth.changePassword")}
        </Button>
      </form>
    </AuthLayout>
  )
}
