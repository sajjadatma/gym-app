import { MailCheck } from "lucide-react"
import { type FormEvent, useState } from "react"
import { translateApiError } from "@/api"
import { LoginService } from "@/client"
import { AuthLayout, BackToLogin } from "@/components/AuthLayout"
import { Button, TextField } from "@/components/M3"
import { useI18n } from "@/i18n"

export function RecoverPasswordPage() {
  const { t } = useI18n()
  const [email, setEmail] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!email.trim() || !/^\S+@\S+\.\S+$/.test(email)) {
      setError(t("validation.email"))
      return
    }
    setLoading(true)
    setError(null)
    try {
      await LoginService.recoverPassword({ path: { email: email.trim() } })
      setSent(true)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title={t("auth.recoverTitle")}
      subtitle={t("auth.recoverSubtitle")}
    >
      {sent ? (
        <div className="stack-sm">
          <div
            className="m3-inline-alert m3-inline-alert--success"
            role="status"
          >
            <MailCheck
              size={18}
              style={{ marginInlineEnd: 6, verticalAlign: "middle" }}
            />
            {t("auth.recoverySent")}
          </div>
          <BackToLogin />
        </div>
      ) : (
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
            error={error ?? undefined}
            required
          />
          <Button type="submit" fullWidth loading={loading}>
            {t("auth.sendReset")}
          </Button>
          <BackToLogin />
        </form>
      )}
    </AuthLayout>
  )
}
