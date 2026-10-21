import { Link } from "@tanstack/react-router"
import { ArrowLeft } from "lucide-react"
import type { ReactNode } from "react"

import { useI18n } from "../i18n"

export function AuthLayout({
  title,
  subtitle,
  children,
  note,
}: {
  title: string
  subtitle: string
  children: ReactNode
  note?: ReactNode
}) {
  const { t } = useI18n()
  return (
    <div className="m3-auth-page">
      <aside className="m3-auth-brand" aria-hidden>
        <div className="m3-auth-brand__logo">
          <span className="m3-auth-brand__mark">ف</span>
          <span>{t("app.name")}</span>
        </div>
        <div className="m3-auth-brand__body">
          <h1>{t("auth.brandTitle")}</h1>
          <p>{t("auth.brandText")}</p>
        </div>
        <div className="m3-auth-brand__footer">{t("app.tagline")}</div>
      </aside>
      <main className="m3-auth-panel">
        <div className="m3-auth-card">
          <div className="m3-auth-card__head">
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          {children}
          {note ? <div className="m3-auth-note">{note}</div> : null}
        </div>
      </main>
    </div>
  )
}

export function BackToLogin() {
  const { t } = useI18n()
  return (
    <Link to="/login" className="row" style={{ gap: 4, fontSize: 12.5 }}>
      <ArrowLeft size={15} />
      {t("auth.backToLogin")}
    </Link>
  )
}
