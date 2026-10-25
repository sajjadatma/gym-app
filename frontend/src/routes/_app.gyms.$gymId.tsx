import {
  createFileRoute,
  Navigate,
  Outlet,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router"
import { useEffect, useRef } from "react"

import { useAuth } from "@/auth"
import { Spinner } from "@/components/M3"
import { useI18n } from "@/i18n"

const STAFF_SECTIONS = new Set([
  "athletes",
  "exercises",
  "templates",
  "programs",
])

function ClubLayout() {
  const { gymId } = Route.useParams()
  const { gyms, activeGymId, setActiveGym, isLoading, isSuperuser } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const gym = gyms.find((item) => item.id === gymId)
  // Sync only when the route parameter changes. Reacting to activeGymId here
  // would immediately re-select the club after an explicit "all clubs" clear.
  const syncedGymId = useRef(activeGymId)
  useEffect(() => {
    if (isLoading || !gym || syncedGymId.current === gymId) return
    syncedGymId.current = gymId
    setActiveGym(gymId)
  }, [gym, gymId, isLoading, setActiveGym])

  const section = pathname.split("/")[3] ?? ""
  const isAdmin = Boolean(
    gym && (isSuperuser || gym.is_owner || gym.my_roles.includes("GYM_ADMIN")),
  )
  const isStaff = Boolean(gym && (isAdmin || gym.my_roles.includes("COACH")))
  const isAthlete = Boolean(gym?.my_roles.includes("ATHLETE"))
  const allowed =
    section === ""
      ? true
      : section === "my"
        ? isAthlete
        : section === "members"
          ? isAdmin
          : STAFF_SECTIONS.has(section)
            ? isStaff
            : true

  useEffect(() => {
    if (isLoading || !gym || activeGymId !== gymId || allowed) return
    navigate({
      to: "/gyms/$gymId",
      params: { gymId },
      replace: true,
    })
  }, [activeGymId, allowed, gym, gymId, isLoading, navigate])

  if (isLoading) return <Spinner label={t("common.loading")} />
  if (!gym) return <Navigate to="/gyms" replace />
  if (activeGymId !== gymId || !allowed) {
    return <Spinner label={t("common.loading")} />
  }
  return <Outlet />
}

export const Route = createFileRoute("/_app/gyms/$gymId")({
  component: ClubLayout,
})
