import { createFileRoute } from "@tanstack/react-router"

import { SuperuserCoachesPage } from "@/pages/SuperuserCoachesPage"

export const Route = createFileRoute("/_app/coaches")({
  component: SuperuserCoachesPage,
})
