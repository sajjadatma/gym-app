import { createFileRoute } from "@tanstack/react-router"

import { parseListSearch, stripListDefaults } from "@/lib/list-search"

import { MembersPage } from "@/pages/MembersPage"

export const Route = createFileRoute("/_app/gyms/$gymId/members")({
  validateSearch: parseListSearch,
  search: { middlewares: [stripListDefaults] },
  component: MembersPage,
})
