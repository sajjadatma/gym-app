import { createFileRoute, Outlet } from "@tanstack/react-router"
import { useEffect, useRef } from "react"

import { useAuth } from "@/auth"

function ClubLayout() {
  const { gymId } = Route.useParams()
  const { activeGymId, setActiveGym } = useAuth()
  // Sync only when the route parameter changes. Depending on activeGymId here
  // would let this effect overwrite a club chosen from the topbar switcher
  // while the URL still points at the previous club.
  const syncedGymId = useRef(activeGymId)
  useEffect(() => {
    if (syncedGymId.current === gymId) return
    syncedGymId.current = gymId
    setActiveGym(gymId)
  }, [gymId, setActiveGym])
  return <Outlet />
}

export const Route = createFileRoute("/_app/gyms/$gymId")({
  component: ClubLayout,
})
