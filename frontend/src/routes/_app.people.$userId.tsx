import { createFileRoute } from "@tanstack/react-router"

import { PersonOverviewPage } from "@/pages/PersonOverviewPage"

type PersonSearch = {
  gym: string
  kind: "ATHLETE" | "COACH"
}

function Page() {
  const { userId } = Route.useParams()
  const { gym, kind } = Route.useSearch()
  return <PersonOverviewPage userId={userId} gymId={gym} kind={kind} />
}

export const Route = createFileRoute("/_app/people/$userId")({
  validateSearch: (search: Record<string, unknown>): PersonSearch => ({
    gym: typeof search.gym === "string" ? search.gym : "",
    kind: search.kind === "COACH" ? "COACH" : "ATHLETE",
  }),
  component: Page,
})
