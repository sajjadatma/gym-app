import { createFileRoute } from "@tanstack/react-router"

import { parseListSearch, stripListDefaults } from "@/lib/list-search"

import { AthletesPage } from "@/pages/AthletesPage"

export const Route = createFileRoute("/_app/gyms/$gymId/athletes/")({
  validateSearch: parseListSearch,
  search: { middlewares: [stripListDefaults] },
  component: AthletesPage,
})
