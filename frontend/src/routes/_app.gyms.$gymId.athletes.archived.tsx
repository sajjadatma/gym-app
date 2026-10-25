import { createFileRoute } from "@tanstack/react-router"

import { parseListSearch, stripListDefaults } from "@/lib/list-search"

import { ArchivedAthletesPage } from "@/pages/ArchivedAthletesPage"

export const Route = createFileRoute("/_app/gyms/$gymId/athletes/archived")({
  validateSearch: parseListSearch,
  search: { middlewares: [stripListDefaults] },
  component: ArchivedAthletesPage,
})
