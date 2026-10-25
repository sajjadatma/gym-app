import { createFileRoute } from "@tanstack/react-router"

import {
  parseGlobalListSearch,
  stripGlobalListDefaults,
} from "@/lib/list-search"

import { SuperuserCoachesPage } from "@/pages/SuperuserCoachesPage"

export const Route = createFileRoute("/_app/coaches")({
  validateSearch: parseGlobalListSearch,
  search: { middlewares: [stripGlobalListDefaults] },
  component: SuperuserCoachesPage,
})
