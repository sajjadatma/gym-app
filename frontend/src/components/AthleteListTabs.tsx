import { Link } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { useI18n } from "@/i18n"

export function AthleteListTabs({ active }: { active: "active" | "archived" }) {
  const { t } = useI18n()
  const { activeGymId } = useAuth()
  return (
    <nav className="m3-tabs" aria-label={t("athletes.title")}>
      <Link
        to="/gyms/$gymId/athletes"
        params={{ gymId: activeGymId! }}
        className={`m3-tabs__tab ${active === "active" ? "is-active" : ""}`}
      >
        {t("athletes.activeList")}
      </Link>
      <Link
        to="/gyms/$gymId/athletes/archived"
        params={{ gymId: activeGymId! }}
        className={`m3-tabs__tab ${active === "archived" ? "is-active" : ""}`}
      >
        {t("athletes.archivedList")}
      </Link>
    </nav>
  )
}
