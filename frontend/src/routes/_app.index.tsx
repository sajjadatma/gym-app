import { createFileRoute, Navigate } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { DashboardPage } from "@/pages/DashboardPage"

function Page() {
  const { activeGymId } = useAuth()
  if (activeGymId) {
    return (
      <Navigate to="/gyms/$gymId" params={{ gymId: activeGymId }} replace />
    )
  }
  return <DashboardPage />
}

export const Route = createFileRoute("/_app/")({
  component: Page,
})
