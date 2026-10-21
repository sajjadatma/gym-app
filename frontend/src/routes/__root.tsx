import {
  createRootRoute,
  HeadContent,
  Outlet,
  useNavigate,
} from "@tanstack/react-router"
import { Home, RefreshCw } from "lucide-react"

import { Button } from "@/components/M3"
import { useI18n } from "@/i18n"

function NotFound() {
  const { t } = useI18n()
  const navigate = useNavigate()
  return (
    <div
      className="m3-auth-page"
      style={{ display: "grid", placeItems: "center" }}
    >
      <div className="m3-auth-card" style={{ textAlign: "center" }}>
        <h1>404</h1>
        <p className="muted" style={{ margin: "10px 0 20px" }}>
          {t("common.noData")}
        </p>
        <Button icon={<Home size={17} />} onClick={() => navigate({ to: "/" })}>
          {t("nav.dashboard")}
        </Button>
      </div>
    </div>
  )
}

function RootError() {
  const { t } = useI18n()
  return (
    <div
      className="m3-auth-page"
      style={{ display: "grid", placeItems: "center" }}
    >
      <div className="m3-auth-card" style={{ textAlign: "center" }}>
        <h1>{t("common.error")}</h1>
        <p className="muted" style={{ margin: "10px 0 20px" }}>
          {t("errors.generic")}
        </p>
        <Button
          icon={<RefreshCw size={17} />}
          onClick={() => window.location.reload()}
        >
          {t("common.retry")}
        </Button>
      </div>
    </div>
  )
}

export const Route = createRootRoute({
  component: () => (
    <>
      <HeadContent />
      <Outlet />
    </>
  ),
  notFoundComponent: NotFound,
  errorComponent: RootError,
})
