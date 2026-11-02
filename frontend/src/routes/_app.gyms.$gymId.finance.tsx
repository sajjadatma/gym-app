import { createFileRoute } from "@tanstack/react-router"

import { FinancePage } from "@/pages/FinancePage"

export const Route = createFileRoute("/_app/gyms/$gymId/finance")({
  component: FinancePage,
})
