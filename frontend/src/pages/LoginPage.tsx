import { Link, useNavigate } from "@tanstack/react-router"
import { LockKeyhole, Mail } from "lucide-react"
import { type FormEvent, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { AuthLayout } from "@/components/AuthLayout"
import { Button, TextField } from "@/components/M3"
import { useI18n } from "@/i18n"

export function LoginPage() {
  const { t } = useI18n()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{
    email?: string
    password?: string
  }>({})
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const errors: typeof fieldErrors = {}
    if (!email.trim()) errors.email = t("validation.required")
    else if (!/^\S+@\S+\.\S+$/.test(email)) errors.email = t("validation.email")
    if (!password) errors.password = t("validation.required")
    setFieldErrors(errors)
    if (Object.keys(errors).length) return
    setLoading(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate({ to: "/" })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title={t("auth.loginTitle")}
      subtitle={t("auth.loginSubtitle")}
      note={t("auth.superAdminHint")}
    >
      <form className="m3-auth-form" onSubmit={handleSubmit} noValidate>
        {error ? (
          <div className="m3-inline-alert" role="alert">
            {error}
          </div>
        ) : null}
        <TextField
          label={t("auth.email")}
          type="email"
          dir="ltr"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          leading={<Mail size={18} />}
          error={fieldErrors.email}
          required
        />
        <TextField
          label={t("auth.password")}
          type="password"
          dir="ltr"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          leading={<LockKeyhole size={18} />}
          error={fieldErrors.password}
          required
        />
        <Button
          type="submit"
          fullWidth
          loading={loading}
          icon={<LockKeyhole size={17} />}
        >
          {loading ? t("auth.loggingIn") : t("auth.login")}
        </Button>
      </form>
      <div className="m3-auth-links">
        <Link to="/recover-password">{t("auth.forgotPassword")}</Link>
      </div>
    </AuthLayout>
  )
}
