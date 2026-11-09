import { createFileRoute, Navigate, Outlet } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { FinanceNav } from "@/components/FinanceNav"
import { Spinner } from "@/components/M3"
import { useI18n } from "@/i18n"

function GymFinanceLayout() {
  const { gymId } = Route.useParams()
  const { activeGymId, gyms, isLoading } = useAuth()
  const { t } = useI18n()
  const gym = gyms.find((item) => item.id === gymId)
  const isAdmin = Boolean(
    gym && (gym.is_owner || gym.my_roles.includes("GYM_ADMIN")),
  )
  if (isLoading || activeGymId !== gymId)
    return <Spinner label={t("common.loading")} />
  if (!gym || !isAdmin)
    return <Navigate to="/gyms/$gymId" params={{ gymId }} replace />
  return (
    <div className="m3-finance-shell">
      <FinanceNav gymId={gymId} />
      <Outlet />
    </div>
  )
}

export const Route = createFileRoute("/_app/gyms/$gymId/finance")({
  component: GymFinanceLayout,
})
