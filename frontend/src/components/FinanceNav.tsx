import { Link, useRouterState } from "@tanstack/react-router"
import {
  BarChart3,
  FileSignature,
  HandCoins,
  LayoutDashboard,
  Percent,
  ReceiptText,
} from "lucide-react"

import { useI18n } from "@/i18n"

type FinanceNavProps = {
  gymId?: string
}

export function FinanceNav({ gymId }: FinanceNavProps) {
  const { t, direction } = useI18n()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const base = gymId ? `/gyms/${gymId}/finance` : "/finance"
  const items = gymId
    ? [
        { to: base, label: t("finance.nav.overview"), icon: LayoutDashboard },
        {
          to: `${base}/contracts`,
          label: t("finance.nav.contracts"),
          icon: FileSignature,
        },
        {
          to: `${base}/sales`,
          label: t("finance.nav.sales"),
          icon: ReceiptText,
        },
        { to: `${base}/taxes`, label: t("finance.nav.taxes"), icon: Percent },
        {
          to: `${base}/settlements`,
          label: t("finance.nav.settlements"),
          icon: HandCoins,
        },
        {
          to: `${base}/reports`,
          label: t("finance.nav.reports"),
          icon: BarChart3,
        },
      ]
    : [
        { to: base, label: t("finance.nav.overview"), icon: LayoutDashboard },
        {
          to: `${base}/platform-contracts`,
          label: t("finance.nav.platformContracts"),
          icon: FileSignature,
        },
        { to: `${base}/taxes`, label: t("finance.nav.taxes"), icon: Percent },
        {
          to: `${base}/reports`,
          label: t("finance.nav.reports"),
          icon: BarChart3,
        },
      ]
  return (
    <nav
      className="m3-finance-nav"
      aria-label={t("finance.nav.label")}
      dir={direction}
    >
      {items.map((item) => {
        const active =
          item.to === base
            ? pathname === base || pathname === `${base}/`
            : pathname.startsWith(item.to)
        const Icon = item.icon
        return (
          <Link
            key={item.to}
            to={item.to as never}
            className={`m3-finance-nav__item ${active ? "is-active" : ""}`}
          >
            <Icon size={18} aria-hidden />
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
