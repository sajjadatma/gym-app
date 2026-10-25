import { createFileRoute } from "@tanstack/react-router"

import { ArchivedAthletesPage } from "@/pages/ArchivedAthletesPage"

export const Route = createFileRoute("/_app/gyms/$gymId/athletes/archived")({
  component: ArchivedAthletesPage,
})
