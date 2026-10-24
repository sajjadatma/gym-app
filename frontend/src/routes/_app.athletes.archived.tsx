import { createFileRoute } from "@tanstack/react-router"

import { ArchivedAthletesPage } from "@/pages/ArchivedAthletesPage"

export const Route = createFileRoute("/_app/athletes/archived")({
  component: ArchivedAthletesPage,
})
