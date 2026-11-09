import { createFileRoute, Navigate, Outlet } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { FinanceNav } from "@/components/FinanceNav"
import { Spinner } from "@/components/M3"
import { useI18n } from "@/i18n"

function FinanceLayout() {
  const { isSuperuser, isLoading } = useAuth()
  const { t } = useI18n()
  if (isLoading) return <Spinner label={t("common.loading")} />
  if (!isSuperuser) return <Navigate to="/" replace />
  return (
    <div className="m3-finance-shell">
      <FinanceNav />
      <Outlet />
    </div>
  )
}

export const Route = createFileRoute("/_app/finance")({
  component: FinanceLayout,
})
