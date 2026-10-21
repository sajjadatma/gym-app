import { createFileRoute } from "@tanstack/react-router"

import { AthleteDetailPage } from "@/pages/AthleteDetailPage"

function Page() {
  const { athleteId } = Route.useParams()
  return <AthleteDetailPage athleteId={athleteId} />
}

export const Route = createFileRoute("/_app/athletes/$athleteId")({
  component: Page,
})
