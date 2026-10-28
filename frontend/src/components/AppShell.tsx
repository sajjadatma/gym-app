import {
  Navigate,
  Outlet,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router"
import {
  Bookmark,
  Building2,
  Check,
  ChevronDown,
  ClipboardList,
  Dumbbell,
  Globe2,
  LayoutDashboard,
  LogOut,
  Moon,
  Sun,
  UserRound,
  Users,
  X,
} from "lucide-react"
import {
  type CSSProperties,
  type ReactNode,
  type RefObject,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"
import { apiAssetUrl } from "../api"
import { type RoleMode, useAuth } from "../auth"
import { type TranslationKey, useI18n } from "../i18n"
import { readableOnColor } from "../lib/brand"
import { useMobileViewport } from "../lib/useMobileViewport"
import { useTheme } from "../theme"
import { Avatar, Button, IconButton, Spinner } from "./M3"
import { OfflineBanner, OfflineState, useOnlineStatus } from "./OnlineStatus"

type NavItem = {
  to: string
  label: TranslationKey
  icon: typeof LayoutDashboard
  params?: Record<string, string>
}

const ROLE_MODE_LABELS: Record<RoleMode, TranslationKey> = {
  GYM_ADMIN: "context.adminMode",
  COACH: "context.coachMode",
  ATHLETE: "context.athleteMode",
}

function useOutsideClose(
  open: boolean,
  close: () => void,
  returnFocus?: RefObject<HTMLButtonElement | null>,
) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const handlePointer = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) close()
    }
    const handleKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return
      event.preventDefault()
      close()
      ;(
        returnFocus?.current ??
        ref.current?.querySelector<HTMLElement>("button")
      )?.focus()
    }
    document.addEventListener("mousedown", handlePointer)
    document.addEventListener("keydown", handleKey)
    return () => {
      document.removeEventListener("mousedown", handlePointer)
      document.removeEventListener("keydown", handleKey)
    }
  }, [open, close, returnFocus?.current])
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
    isLoading,
    isSuperuser,
    setActiveGym,
    logout,
    refresh,
  } = useAuth()
  const { t, locale, setLocale } = useI18n()
  const { theme, setTheme } = useTheme()
  const online = useOnlineStatus()
  const isMobile = useMobileViewport()
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const [profileOpen, setProfileOpen] = useState(false)
  const accountTriggerRef = useRef<HTMLButtonElement>(null)
  const closeProfile = useCallback(() => setProfileOpen(false), [])
  const closeAccount = useCallback(() => {
    setProfileOpen(false)
    window.requestAnimationFrame(() => accountTriggerRef.current?.focus())
  }, [])
  const profileRef = useOutsideClose(
    profileOpen && !isMobile,
    closeProfile,
    accountTriggerRef,
  )
  const sheetRef = useOutsideClose(
    profileOpen && isMobile,
    closeProfile,
    accountTriggerRef,
  )

  useEffect(() => {
    if (!profileOpen || !isMobile) return
    sheetRef.current?.querySelector<HTMLElement>("button")?.focus()
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previous
    }
  }, [isMobile, profileOpen, sheetRef])

  useEffect(() => {
    if (!profileOpen || !isMobile) return
    const handleTab = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return
      const root = sheetRef.current
      if (!root) return
      const items = Array.from(
        root.querySelectorAll<HTMLElement>(
          "button:not([disabled]), a[href], input:not([disabled])",
        ),
      )
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener("keydown", handleTab, true)
    return () => document.removeEventListener("keydown", handleTab, true)
  }, [isMobile, profileOpen, sheetRef])

  useEffect(() => {
    const handler = () => navigate({ to: "/change-password" as never })
    window.addEventListener("gym:password-required", handler)
    return () => window.removeEventListener("gym:password-required", handler)
  }, [navigate])

  useEffect(() => {
    if (isLoading || !isSuperuser) return
    if (gyms.length === 0 && pathname !== "/gyms") {
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
    if (!online) return <OfflineState onRetry={() => void refresh()} />
    return <Navigate to="/login" replace />
  }

  const clubParams = activeGymId ? { gymId: activeGymId } : undefined
  const clubPath = (suffix: string) => `/gyms/$gymId${suffix}`
  let navItems: NavItem[] = []
  if (!activeGym) {
    navItems = isSuperuser
      ? [
          { to: "/", label: "nav.dashboard", icon: LayoutDashboard },
          { to: "/gyms", label: "nav.gyms", icon: Building2 },
          { to: "/coaches", label: "nav.coaches", icon: UserRound },
          { to: "/athletes", label: "nav.athletes", icon: Users },
        ]
      : [{ to: "/", label: "nav.dashboard", icon: LayoutDashboard }]
  } else if (activeRole === "ATHLETE") {
    navItems = [
      {
        to: clubPath(""),
        params: clubParams,
        label: "nav.dashboard",
        icon: LayoutDashboard,
      },
      {
        to: clubPath("/my"),
        params: clubParams,
        label: "nav.myProgram",
        icon: ClipboardList,
      },
      {
        to: clubPath("/my/profile"),
        params: clubParams,
        label: "nav.myProfile",
        icon: UserRound,
      },
    ]
  } else if (activeRole === "COACH") {
    navItems = [
      {
        to: clubPath(""),
        params: clubParams,
        label: "nav.dashboard",
        icon: LayoutDashboard,
      },
      {
        to: clubPath("/athletes"),
        params: clubParams,
        label: "nav.athletes",
        icon: Users,
      },
      {
        to: clubPath("/exercises"),
        params: clubParams,
        label: "nav.exercises",
        icon: Dumbbell,
      },
      {
        to: clubPath("/templates"),
        params: clubParams,
        label: "nav.templates",
        icon: Bookmark,
      },
    ]
  } else {
    navItems = [
      {
        to: clubPath(""),
        params: clubParams,
        label: "nav.dashboard",
        icon: LayoutDashboard,
      },
      ...(isSuperuser
        ? []
        : ([{ to: "/gyms", label: "nav.gyms", icon: Building2 }] as NavItem[])),
      {
        to: clubPath("/athletes"),
        params: clubParams,
        label: "nav.athletes",
        icon: Users,
      },
      {
        to: clubPath("/members"),
        params: clubParams,
        label: "nav.members",
        icon: UserRound,
      },
      {
        to: clubPath("/exercises"),
        params: clubParams,
        label: "nav.exercises",
        icon: Dumbbell,
      },
      {
        to: clubPath("/templates"),
        params: clubParams,
        label: "nav.templates",
        icon: Bookmark,
      },
    ]
  }

  const resolve = (to: string) =>
    activeGymId ? to.replace("$gymId", activeGymId) : to
  const isActive = (to: string) => {
    if (to === "/") return pathname === "/"
    if (to.endsWith("/my")) {
      const resolved = resolve(to)
      return (
        pathname === resolved ||
        pathname === `${resolved}/` ||
        pathname.startsWith(`${resolved}/programs`)
      )
    }
    if (to === "/gyms") return pathname === "/gyms" || pathname === "/gyms/"
    if (to === "/gyms/$gymId") {
      const resolved = resolve(to)
      return pathname === resolved || pathname === `${resolved}/`
    }
    const resolved = resolve(to)
    return pathname === resolved || pathname.startsWith(`${resolved}/`)
  }

  const go = (item: NavItem) =>
    navigate({ to: item.to as never, params: item.params as never })

  const roleLabel = (role: RoleMode) => t(ROLE_MODE_LABELS[role])
  const clubPrimary = activeGym?.brand_primary_color ?? undefined
  const brandStyle = clubPrimary
    ? ({
        "--club-primary": clubPrimary,
        "--club-on-primary": readableOnColor(clubPrimary),
        "--club-accent": activeGym?.brand_accent_color ?? clubPrimary,
      } as CSSProperties)
    : undefined
  const brandMark = activeGym?.logo_url ? (
    <img
      className="m3-nav-rail__logo"
      src={apiAssetUrl(activeGym.logo_url)}
      alt=""
      onError={(event) => {
        event.currentTarget.style.display = "none"
      }}
    />
  ) : (
    <span>A</span>
  )

  const currentRoleLabel = activeRole
    ? roleLabel(activeRole)
    : isSuperuser
      ? t("context.superAdmin")
      : null

  const accountPanel = (
    <div className="m3-account">
      <header className="m3-account__header">
        <Avatar name={me.full_name ?? me.email} />
        <div className="m3-account__identity">
          <strong>{me.full_name ?? me.email}</strong>
          <span dir="ltr">{me.email}</span>
        </div>
        {isMobile ? (
          <IconButton label={t("common.close")} onClick={closeAccount}>
            <X size={18} aria-hidden />
          </IconButton>
        ) : null}
      </header>

      <div className="m3-account__role-row">
        <span className="m3-account__label">{t("context.activeRole")}</span>
        <span className="m3-account__role">{currentRoleLabel}</span>
      </div>

      <fieldset className="m3-account__section">
        <legend className="m3-account__label">{t("shell.language")}</legend>
        <div className="m3-account__segmented">
          <button
            type="button"
            className={`m3-account__segment ${locale === "fa" ? "is-active" : ""}`}
            aria-pressed={locale === "fa"}
            onClick={() => {
              setLocale("fa")
              closeAccount()
            }}
          >
            {t("shell.languageFa")}
          </button>
          <button
            type="button"
            className={`m3-account__segment ${locale === "en" ? "is-active" : ""}`}
            aria-pressed={locale === "en"}
            onClick={() => {
              setLocale("en")
              closeAccount()
            }}
          >
            {t("shell.languageEn")}
          </button>
        </div>
      </fieldset>

      <fieldset className="m3-account__section">
        <legend className="m3-account__label">{t("shell.theme")}</legend>
        <div className="m3-account__segmented">
          <button
            type="button"
            className={`m3-account__segment ${theme === "light" ? "is-active" : ""}`}
            aria-pressed={theme === "light"}
            onClick={() => {
              setTheme("light")
              closeAccount()
            }}
          >
            <Sun size={15} aria-hidden />
            {t("shell.themeLight")}
          </button>
          <button
            type="button"
            className={`m3-account__segment ${theme === "dark" ? "is-active" : ""}`}
            aria-pressed={theme === "dark"}
            onClick={() => {
              setTheme("dark")
              closeAccount()
            }}
          >
            <Moon size={15} aria-hidden />
            {t("shell.themeDark")}
          </button>
        </div>
      </fieldset>

      <div className="m3-account__separator" />

      <button
        type="button"
        className="m3-account__item"
        onClick={() => {
          closeAccount()
          navigate({ to: "/profile" as never })
        }}
      >
        <UserRound size={17} aria-hidden />
        <span>{t("shell.profile")}</span>
      </button>

      <div className="m3-account__separator" />

      <button
        type="button"
        className="m3-account__item m3-account__item--danger"
        onClick={() => {
          closeProfile()
          void logout()
        }}
      >
        <LogOut size={17} aria-hidden />
        <span>{t("shell.logout")}</span>
      </button>
    </div>
  )

  return (
    <div
      className="m3-app-shell"
      data-club-branded={clubPrimary ? "true" : undefined}
      style={brandStyle}
    >
      <nav className="m3-nav-rail" aria-label={t("shell.menu")}>
        <div className="m3-nav-rail__brand" aria-hidden>
          {brandMark}
        </div>
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.to}
              type="button"
              className={`m3-nav-rail__item ${isActive(item.to) ? "is-active" : ""}`}
              onClick={() => go(item)}
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
        <OfflineBanner />
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
              {brandMark}
            </div>
            <span>{t("app.name")}</span>
          </div>

          <div className="m3-topbar__context">
            {isSuperuser && activeGym ? (
              <Button
                variant="text"
                size="sm"
                className="m3-topbar__back"
                icon={
                  isMobile ? (
                    <Globe2 size={18} aria-hidden />
                  ) : (
                    <LayoutDashboard size={16} aria-hidden />
                  )
                }
                aria-label={t("dashboard.globalDashboard")}
                onClick={() => {
                  setActiveGym(null)
                  navigate({ to: "/" as never })
                }}
              >
                {t("dashboard.globalDashboard")}
              </Button>
            ) : null}
            {activeGym ? (
              gyms.length > 1 || isSuperuser ? (
                <Dropdown
                  label={t("context.switchGym")}
                  trigger={
                    <span className="m3-topbar__gym m3-topbar__gym--switch">
                      <Building2 size={15} />
                      <span>{activeGym.name}</span>
                      <ChevronDown
                        size={14}
                        className="m3-topbar__chevron"
                        aria-hidden
                      />
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
                        navigate({
                          to: "/gyms/$gymId" as never,
                          params: { gymId: gym.id } as never,
                        })
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
          </div>

          <div className="m3-topbar__spacer" />

          <div className="m3-topbar__actions" ref={profileRef}>
            <button
              ref={accountTriggerRef}
              type="button"
              className="m3-account-trigger"
              aria-haspopup="dialog"
              aria-expanded={profileOpen}
              aria-controls={profileOpen ? "account-panel" : undefined}
              aria-label={t("nav.account")}
              onClick={() => setProfileOpen((value) => !value)}
            >
              <Avatar name={me.full_name ?? me.email} />
              <span className="m3-account-trigger__text">
                <strong>{me.full_name ?? me.email}</strong>
              </span>
              <ChevronDown
                size={15}
                className="m3-account-trigger__chevron"
                aria-hidden
              />
            </button>
            {profileOpen && !isMobile ? (
              <div
                id="account-panel"
                className="m3-menu m3-account-popover"
                role="dialog"
                aria-label={t("nav.account")}
              >
                {accountPanel}
              </div>
            ) : null}
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
              onClick={() => go(item)}
              aria-current={isActive(item.to) ? "page" : undefined}
            >
              <Icon size={20} strokeWidth={1.9} />
              <span>{t(item.label)}</span>
            </button>
          )
        })}
      </nav>

      {profileOpen && isMobile ? (
        <>
          <div className="m3-account-scrim" aria-hidden />
          <div
            ref={sheetRef}
            id="account-panel"
            className="m3-account-sheet"
            role="dialog"
            aria-modal="true"
            aria-label={t("nav.account")}
            tabIndex={-1}
          >
            {accountPanel}
          </div>
        </>
      ) : null}
    </div>
  )
}
