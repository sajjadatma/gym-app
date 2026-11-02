import { createFileRoute } from "@tanstack/react-router"

import { CoachEarningsPage } from "@/pages/CoachEarningsPage"

export const Route = createFileRoute("/_app/gyms/$gymId/my/earnings")({
  component: CoachEarningsPage,
})
