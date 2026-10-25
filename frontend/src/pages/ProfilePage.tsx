import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  Building2,
  Check,
  Globe2,
  KeyRound,
  LogOut,
  Moon,
  Save,
  ShieldCheck,
  Sun,
} from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { UsersService } from "@/client"
import {
  Avatar,
  Button,
  Card,
  Chip,
  PageHeader,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"
import { useTheme } from "@/theme"

export function ProfilePage() {
  const { t, locale, setLocale } = useI18n()
  const { theme, setTheme } = useTheme()
  const { me, refresh, logout, activeGymId, setActiveGym } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { show } = useSnackbar()
  const [form, setForm] = useState({
    full_name: me?.full_name ?? "",
    email: me?.email ?? "",
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!me) return null

  async function save() {
    setSaving(true)
    setError(null)
    try {
      await UsersService.updateUserMe({
        body: {
          full_name: form.full_name || null,
          email: form.email,
        },
      })
      await refresh()
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      show(t("profile.saved"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t("profile.title")}
        subtitle={t("profile.subtitle")}
        actions={
          <Button
            variant="outlined"
            icon={<LogOut size={16} />}
            onClick={logout}
          >
            {t("shell.logout")}
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
              <h2 className="m3-section__title">{t("profile.title")}</h2>
              <p className="m3-section__subtitle">
                {me.is_superuser ? t("profile.superAdmin") : ""}
              </p>
            </div>
            <Avatar name={me.full_name ?? me.email} />
          </div>
          <div className="stack">
            <TextField
              label={t("profile.name")}
              value={form.full_name}
              onChange={(event) =>
                setForm({ ...form, full_name: event.target.value })
              }
            />
            <TextField
              label={t("profile.email")}
              type="email"
              dir="ltr"
              value={form.email}
              onChange={(event) =>
                setForm({ ...form, email: event.target.value })
              }
              helper={t("profile.emailHint")}
              required
            />
            <div>
              <Button icon={<Save size={16} />} onClick={save} loading={saving}>
                {t("profile.save")}
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("profile.security")}</h2>
              <p className="m3-section__subtitle">
                {t("profile.securityHint")}
              </p>
            </div>
            <ShieldCheck size={22} className="muted" />
          </div>
          <p className="muted" style={{ fontSize: 12.5 }}>
            {me.email}
          </p>
          <div className="row" style={{ marginTop: 14 }}>
            <Button
              variant="tonal"
              icon={<KeyRound size={16} />}
              onClick={() => navigate({ to: "/change-password" })}
            >
              {t("auth.changePassword")}
            </Button>
          </div>
        </Card>
      </div>

      <div style={{ height: 16 }} />

      <div className="grid-2">
        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("profile.language")}</h2>
              <p className="m3-section__subtitle">
                {t("profile.languageHint")}
              </p>
            </div>
            <Globe2 size={22} className="muted" />
          </div>
          <div className="row">
            <Chip selected={locale === "fa"} onClick={() => setLocale("fa")}>
              {t("shell.languageFa")}
              {locale === "fa" ? <Check size={14} /> : null}
            </Chip>
            <Chip selected={locale === "en"} onClick={() => setLocale("en")}>
              {t("shell.languageEn")}
              {locale === "en" ? <Check size={14} /> : null}
            </Chip>
          </div>
          <div className="m3-section__header" style={{ marginTop: 18 }}>
            <div>
              <h2 className="m3-section__title">{t("shell.theme")}</h2>
            </div>
          </div>
          <div className="row">
            <Chip
              selected={theme === "light"}
              onClick={() => setTheme("light")}
              icon={<Sun size={14} />}
            >
              {t("shell.themeLight")}
            </Chip>
            <Chip
              selected={theme === "dark"}
              onClick={() => setTheme("dark")}
              icon={<Moon size={14} />}
            >
              {t("shell.themeDark")}
            </Chip>
          </div>
        </Card>

        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("profile.memberships")}</h2>
              <p className="m3-section__subtitle">{t("app.tagline")}</p>
            </div>
            <Building2 size={22} className="muted" />
          </div>
          {me.gyms.length ? (
            <div className="stack-sm">
              {me.gyms.map((gym) => (
                <button
                  key={gym.gym_id}
                  type="button"
                  className="m3-file-row"
                  style={{
                    border: 0,
                    width: "100%",
                    textAlign: "start",
                    fontFamily: "inherit",
                    background:
                      gym.gym_id === activeGymId
                        ? "var(--m3-secondary-container)"
                        : undefined,
                  }}
                  onClick={() => {
                    setActiveGym(gym.gym_id)
                    navigate({
                      to: "/gyms/$gymId",
                      params: { gymId: gym.gym_id },
                    })
                  }}
                >
                  <Building2 size={17} className="muted" />
                  <span className="m3-file-row__name">{gym.gym_name}</span>
                  <span className="muted" style={{ fontSize: 11 }}>
                    {gym.is_owner ? t("context.owner") : ""}{" "}
                    {gym.roles
                      .map((role) =>
                        role === "GYM_ADMIN"
                          ? t("context.gymAdmin")
                          : role === "COACH"
                            ? t("context.coach")
                            : t("context.athlete"),
                      )
                      .join(" · ")}
                  </span>
                  {gym.gym_id === activeGymId ? <Check size={15} /> : null}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">{t("profile.noMemberships")}</p>
          )}
        </Card>
      </div>
    </>
  )
}
