import { createFileRoute } from "@tanstack/react-router"

import { CoachPlanPage } from "@/pages/finance/CoachPlanPage"

export const Route = createFileRoute("/_app/gyms/$gymId/coach-plan")({
  component: () => {
    const { gymId } = Route.useParams()
    return <CoachPlanPage gymId={gymId} />
  },
})
