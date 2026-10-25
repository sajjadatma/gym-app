import { createFileRoute, Navigate } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { ClubRedirect } from "@/components/ClubRedirect"
import { SuperuserAthletesPage } from "@/pages/SuperuserAthletesPage"

function Page() {
  const { isSuperuser, activeGymId } = useAuth()
  if (activeGymId) return <ClubRedirect to="/gyms/$gymId/athletes" />
  if (isSuperuser) return <SuperuserAthletesPage />
  return <Navigate to="/" replace />
}

export const Route = createFileRoute("/_app/athletes/")({
  component: Page,
})
