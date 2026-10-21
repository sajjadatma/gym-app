import { useNavigate } from "@tanstack/react-router"
import { KeyRound } from "lucide-react"
import { type FormEvent, useState } from "react"
import { translateApiError } from "@/api"
import { LoginService } from "@/client"
import { AuthLayout, BackToLogin } from "@/components/AuthLayout"
import { Button, TextField } from "@/components/M3"
import { useI18n } from "@/i18n"

export function ResetPasswordPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const token = new URLSearchParams(window.location.search).get("token") ?? ""
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(
    token ? null : t("auth.inviteInvalid"),
  )
  const [fieldErrors, setFieldErrors] = useState<{
    password?: string
    confirm?: string
  }>({})
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const errors: typeof fieldErrors = {}
    if (password.length < 8) errors.password = t("validation.minPassword")
    if (confirm !== password) errors.confirm = t("validation.passwordMismatch")
    setFieldErrors(errors)
    if (Object.keys(errors).length || !token) return
    setLoading(true)
    setError(null)
    try {
      await LoginService.resetPassword({
        body: { token, new_password: password },
      })
      navigate({ to: "/login" })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout title={t("auth.resetTitle")} subtitle={t("auth.resetSubtitle")}>
      <form className="m3-auth-form" onSubmit={handleSubmit} noValidate>
        {error ? (
          <div className="m3-inline-alert" role="alert">
            {error}
          </div>
        ) : null}
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
        <Button type="submit" fullWidth loading={loading} disabled={!token}>
          {t("auth.changePassword")}
        </Button>
        <BackToLogin />
      </form>
    </AuthLayout>
  )
}
