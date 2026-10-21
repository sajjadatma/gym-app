import { createFileRoute } from "@tanstack/react-router"

import { AthletesPage } from "@/pages/AthletesPage"

export const Route = createFileRoute("/_app/athletes/")({
  component: AthletesPage,
})
