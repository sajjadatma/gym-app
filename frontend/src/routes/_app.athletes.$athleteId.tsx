import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

function Page() {
  const { athleteId } = Route.useParams()
  return (
    <ClubRedirect
      to="/gyms/$gymId/athletes/$athleteId"
      params={{ athleteId }}
    />
  )
}

export const Route = createFileRoute("/_app/athletes/$athleteId")({
  component: Page,
})
