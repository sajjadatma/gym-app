import { createFileRoute, Outlet } from "@tanstack/react-router"
import { useEffect } from "react"

import { useAuth } from "@/auth"

function ClubLayout() {
  const { gymId } = Route.useParams()
  const { activeGymId, setActiveGym } = useAuth()
  useEffect(() => {
    if (activeGymId !== gymId) setActiveGym(gymId)
  }, [gymId, activeGymId, setActiveGym])
  return <Outlet />
}

export const Route = createFileRoute("/_app/gyms/$gymId")({
  component: ClubLayout,
})
