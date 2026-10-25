import { createFileRoute } from "@tanstack/react-router"

import { AthletesPage } from "@/pages/AthletesPage"

export const Route = createFileRoute("/_app/gyms/$gymId/athletes/")({
  component: AthletesPage,
})
