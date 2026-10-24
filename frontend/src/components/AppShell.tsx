import { Outlet, useNavigate, useRouterState } from "@tanstack/react-router"
import {
  Bookmark,
  Building2,
  Check,
  ClipboardList,
  Dumbbell,
  Globe2,
  LayoutDashboard,
  LogOut,
  Moon,
  Sun,
  UserRound,
  Users,
} from "lucide-react"
import { type ReactNode, useEffect, useRef, useState } from "react"

import { type RoleMode, useAuth } from "../auth"
import { type TranslationKey, useI18n } from "../i18n"
import { useTheme } from "../theme"
import { Avatar, IconButton, Spinner } from "./M3"

type NavItem = {
  to: string
  label: TranslationKey
  icon: typeof LayoutDashboard
}

const ROLE_MODE_LABELS: Record<RoleMode, TranslationKey> = {
  GYM_ADMIN: "context.adminMode",
  COACH: "context.coachMode",
  ATHLETE: "context.athleteMode",
}

function useOutsideClose(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const handler = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) close()
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [open, close])
  return ref
}

function Dropdown({
  trigger,
  children,
  align = "end",
  label,
}: {
  trigger: ReactNode
  children: ReactNode
  align?: "start" | "end"
  label: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useOutsideClose(open, () => setOpen(false))
  return (
    <div className="m3-menu-anchor" ref={ref}>
      <button
        type="button"
        className="m3-text-button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
      >
        {trigger}
      </button>
      {open ? (
        <div
          className="m3-menu"
          role="menu"
          style={
            align === "start"
              ? { insetInlineStart: 0, insetInlineEnd: "auto" }
              : undefined
          }
          onClick={(event) => {
            if ((event.target as HTMLElement).closest('[role="menuitem"]')) {
              setOpen(false)
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false)
          }}
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}

export function AppShell() {
  const {
    me,
    gyms,
    activeGym,
    activeGymId,
    activeRole,
    availableRoles,
    isLoading,
    isSuperuser,
    isOwner,
    setActiveGym,
    setActiveRole,
    logout,
  } = useAuth()
  const { t, locale, setLocale } = useI18n()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useOutsideClose(profileOpen, () => setProfileOpen(false))

  useEffect(() => {
    const handler = () => navigate({ to: "/change-password" as never })
    window.addEventListener("gym:password-required", handler)
    return () => window.removeEventListener("gym:password-required", handler)
  }, [navigate])

  useEffect(() => {
    if (
      !isLoading &&
      isSuperuser &&
      gyms.length === 0 &&
      pathname !== "/gyms"
    ) {
      navigate({ to: "/gyms" as never })
    }
  }, [gyms.length, isLoading, isSuperuser, navigate, pathname])

  if (isLoading) {
    return (
      <div
        style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}
      >
        <Spinner label={t("common.loading")} />
      </div>
    )
  }

  if (!me) {
    return null
  }

  let navItems: NavItem[] = []
  if (!activeGym) {
    navItems = isSuperuser
      ? [
          { to: "/", label: "nav.dashboard", icon: LayoutDashboard },
          { to: "/gyms", label: "nav.gyms", icon: Building2 },
        ]
      : [{ to: "/", label: "nav.dashboard", icon: LayoutDashboard }]
  } else if (activeRole === "ATHLETE") {
    navItems = [
      { to: "/my", label: "nav.myProgram", icon: ClipboardList },
      { to: "/my/profile", label: "nav.myProfile", icon: UserRound },
    ]
  } else if (activeRole === "COACH") {
    navItems = [
      { to: "/", label: "nav.dashboard", icon: LayoutDashboard },
      { to: "/athletes", label: "nav.athletes", icon: Users },
      { to: "/exercises", label: "nav.exercises", icon: Dumbbell },
      { to: "/templates", label: "nav.templates", icon: Bookmark },
    ]
  } else {
    navItems = [
      { to: "/", label: "nav.dashboard", icon: LayoutDashboard },
      { to: "/gyms", label: "nav.gyms", icon: Building2 },
      { to: "/athletes", label: "nav.athletes", icon: Users },
      { to: "/members", label: "nav.members", icon: UserRound },
      { to: "/exercises", label: "nav.exercises", icon: Dumbbell },
      { to: "/templates", label: "nav.templates", icon: Bookmark },
    ]
  }

  const isActive = (to: string) => {
    if (to === "/") return pathname === "/"
    if (to === "/my")
      return pathname === "/my" || pathname.startsWith("/my/programs")
    return pathname.startsWith(to)
  }

  const go = (to: string) => navigate({ to: to as never })

  const roleLabel = (role: RoleMode) => t(ROLE_MODE_LABELS[role])

  return (
    <div className="m3-app-shell">
      <nav className="m3-nav-rail" aria-label={t("shell.menu")}>
        <div className="m3-nav-rail__brand" aria-hidden>
          ف
        </div>
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.to}
              type="button"
              className={`m3-nav-rail__item ${isActive(item.to) ? "is-active" : ""}`}
              onClick={() => go(item.to)}
              aria-current={isActive(item.to) ? "page" : undefined}
            >
              <span className="m3-nav-rail__icon">
                <Icon size={21} strokeWidth={1.9} />
              </span>
              <span>{t(item.label)}</span>
            </button>
          )
        })}
        <div className="m3-nav-rail__spacer" />
        <button
          type="button"
          className="m3-nav-rail__item"
          onClick={() => setProfileOpen((value) => !value)}
        >
          <span className="m3-nav-rail__icon">
            <Avatar name={me.full_name ?? me.email} />
          </span>
          <span>{t("nav.account")}</span>
        </button>
      </nav>

      <div className="m3-app-body">
        <header className="m3-topbar">
          <div className="m3-topbar__brand">
            <div
              className="m3-nav-rail__brand"
              style={{
                width: 38,
                height: 38,
                fontSize: 15,
                margin: 0,
                borderRadius: 13,
              }}
            >
              ف
            </div>
            <span>{t("app.name")}</span>
          </div>

          <div className="m3-topbar__context">
            {activeGym ? (
              gyms.length > 1 || isSuperuser ? (
                <Dropdown
                  label={t("context.switchGym")}
                  trigger={
                    <span className="m3-topbar__gym">
                      <Building2 size={15} />
                      <span>{activeGym.name}</span>
                    </span>
                  }
                >
                  <div className="m3-menu__label">{t("context.activeGym")}</div>
                  {gyms.map((gym) => (
                    <button
                      key={gym.id}
                      type="button"
                      role="menuitem"
                      className={`m3-menu__item ${gym.id === activeGymId ? "is-active" : ""}`}
                      onClick={() => {
                        setActiveGym(gym.id)
                        navigate({ to: "/" as never })
                      }}
                    >
                      <Building2 size={16} />
                      <span className="truncate">{gym.name}</span>
                      {gym.id === activeGymId ? (
                        <Check
                          size={15}
                          style={{ marginInlineStart: "auto" }}
                        />
                      ) : null}
                    </button>
                  ))}
                  {isSuperuser ? (
                    <>
                      <div className="m3-menu__separator" />
                      <button
                        type="button"
                        role="menuitem"
                        className="m3-menu__item"
                        onClick={() => {
                          setActiveGym(null)
                          navigate({ to: "/" as never })
                        }}
                      >
                        <Building2 size={16} />
                        <span>{t("context.allClubs")}</span>
                      </button>
                    </>
                  ) : null}
                </Dropdown>
              ) : (
                <span className="m3-topbar__gym">
                  <Building2 size={15} />
                  <span>{activeGym.name}</span>
                </span>
              )
            ) : null}

            {activeGym && availableRoles.length > 1 ? (
              <Dropdown
                label={t("context.switchRole")}
                trigger={
                  <span className="m3-topbar__role">
                    {activeRole ? roleLabel(activeRole) : ""}
                  </span>
                }
              >
                <div className="m3-menu__label">{t("context.activeRole")}</div>
                {availableRoles.map((role) => (
                  <button
                    key={role}
                    type="button"
                    role="menuitem"
                    className={`m3-menu__item ${activeRole === role ? "is-active" : ""}`}
                    onClick={() => {
                      setActiveRole(role)
                      navigate({
                        to:
                          role === "ATHLETE"
                            ? ("/my" as never)
                            : ("/" as never),
                      })
                    }}
                  >
                    {roleLabel(role)}
                    {activeRole === role ? (
                      <Check size={15} style={{ marginInlineStart: "auto" }} />
                    ) : null}
                  </button>
                ))}
              </Dropdown>
            ) : activeGym && activeRole ? (
              <span className="m3-topbar__role">
                {roleLabel(activeRole)}
                {isOwner ? ` · ${t("context.owner")}` : ""}
              </span>
            ) : null}
          </div>

          <div className="m3-topbar__spacer" />

          <div className="m3-topbar__actions" ref={profileRef}>
            <div className="m3-menu-anchor">
              <IconButton
                label={t("nav.account")}
                onClick={() => setProfileOpen((value) => !value)}
                aria-expanded={profileOpen}
              >
                <Avatar name={me.full_name ?? me.email} />
              </IconButton>
              {profileOpen ? (
                <div className="m3-menu" role="menu">
                  <div style={{ padding: "10px 12px 6px" }}>
                    <div style={{ fontSize: 13, fontWeight: 700 }}>
                      {me.full_name ?? me.email}
                    </div>
                    <div className="muted" style={{ fontSize: 11 }}>
                      {me.email}
                      {isSuperuser ? ` · ${t("context.superAdmin")}` : ""}
                    </div>
                  </div>
                  <div className="m3-menu__separator" />
                  <button
                    type="button"
                    role="menuitem"
                    className="m3-menu__item"
                    onClick={() => {
                      setProfileOpen(false)
                      navigate({ to: "/profile" as never })
                    }}
                  >
                    <UserRound size={16} />
                    {t("shell.profile")}
                  </button>
                  <div className="m3-menu__separator" />
                  <div className="m3-menu__label">{t("shell.language")}</div>
                  <button
                    type="button"
                    className={`m3-menu__item ${locale === "fa" ? "is-active" : ""}`}
                    onClick={() => {
                      setLocale("fa")
                      setProfileOpen(false)
                    }}
                  >
                    <Globe2 size={16} />
                    {t("shell.languageFa")}
                    {locale === "fa" ? (
                      <Check size={15} style={{ marginInlineStart: "auto" }} />
                    ) : null}
                  </button>
                  <button
                    type="button"
                    className={`m3-menu__item ${locale === "en" ? "is-active" : ""}`}
                    onClick={() => {
                      setLocale("en")
                      setProfileOpen(false)
                    }}
                  >
                    <Globe2 size={16} />
                    {t("shell.languageEn")}
                    {locale === "en" ? (
                      <Check size={15} style={{ marginInlineStart: "auto" }} />
                    ) : null}
                  </button>
                  <div className="m3-menu__separator" />
                  <div className="m3-menu__label">{t("shell.theme")}</div>
                  <button
                    type="button"
                    className={`m3-menu__item ${theme === "light" ? "is-active" : ""}`}
                    onClick={() => {
                      setTheme("light")
                      setProfileOpen(false)
                    }}
                  >
                    <Sun size={16} />
                    {t("shell.themeLight")}
                  </button>
                  <button
                    type="button"
                    className={`m3-menu__item ${theme === "dark" ? "is-active" : ""}`}
                    onClick={() => {
                      setTheme("dark")
                      setProfileOpen(false)
                    }}
                  >
                    <Moon size={16} />
                    {t("shell.themeDark")}
                  </button>
                  <div className="m3-menu__separator" />
                  <button
                    type="button"
                    className="m3-menu__item"
                    onClick={logout}
                  >
                    <LogOut size={16} />
                    {t("shell.logout")}
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main className="m3-main">
          <Outlet />
        </main>
      </div>

      <nav className="m3-mobile-nav" aria-label={t("shell.menu")}>
        {navItems.slice(0, 6).map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.to}
              type="button"
              className={`m3-mobile-nav__item ${isActive(item.to) ? "is-active" : ""}`}
              onClick={() => go(item.to)}
              aria-current={isActive(item.to) ? "page" : undefined}
            >
              <Icon size={20} strokeWidth={1.9} />
              <span>{t(item.label)}</span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}
