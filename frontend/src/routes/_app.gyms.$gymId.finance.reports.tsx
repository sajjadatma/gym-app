import { createFileRoute } from "@tanstack/react-router"

import { FinanceReportsPage } from "@/pages/finance/FinanceReportsPage"

export const Route = createFileRoute("/_app/gyms/$gymId/finance/reports")({
  component: () => {
    const { gymId } = Route.useParams()
    return <FinanceReportsPage gymId={gymId} />
  },
})
