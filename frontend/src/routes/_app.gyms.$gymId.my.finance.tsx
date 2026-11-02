import { createFileRoute } from "@tanstack/react-router"

import { AthleteFinancePage } from "@/pages/AthleteFinancePage"

export const Route = createFileRoute("/_app/gyms/$gymId/my/finance")({
  component: AthleteFinancePage,
})
