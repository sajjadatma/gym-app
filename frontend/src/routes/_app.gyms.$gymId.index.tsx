import { createFileRoute } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { DashboardPage } from "@/pages/DashboardPage"
import { GymDetailPage } from "@/pages/GymDetailPage"

function ClubWorkspace() {
  const { gymId } = Route.useParams()
  const { isSuperuser } = useAuth()
  if (!isSuperuser) return <GymDetailPage gymId={gymId} />
  return <DashboardPage />
}

export const Route = createFileRoute("/_app/gyms/$gymId/")({
  component: ClubWorkspace,
})
