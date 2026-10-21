import { createFileRoute } from "@tanstack/react-router"

import { GymDetailPage } from "@/pages/GymDetailPage"

function Page() {
  const { gymId } = Route.useParams()
  return <GymDetailPage gymId={gymId} />
}

export const Route = createFileRoute("/_app/gyms/$gymId")({
  component: Page,
})
