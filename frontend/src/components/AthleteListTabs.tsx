import { Link } from "@tanstack/react-router"

import { useI18n } from "@/i18n"

export function AthleteListTabs({ active }: { active: "active" | "archived" }) {
  const { t } = useI18n()
  return (
    <nav className="m3-tabs" aria-label={t("athletes.title")}>
      <Link
        to="/athletes"
        className={`m3-tabs__tab ${active === "active" ? "is-active" : ""}`}
      >
        {t("athletes.activeList")}
      </Link>
      <Link
        to="/athletes/archived"
        className={`m3-tabs__tab ${active === "archived" ? "is-active" : ""}`}
      >
        {t("athletes.archivedList")}
      </Link>
    </nav>
  )
}
