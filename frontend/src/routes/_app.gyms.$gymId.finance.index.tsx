import { createFileRoute } from "@tanstack/react-router"

import { FinanceOverviewPage } from "@/pages/finance/FinanceOverviewPage"

export const Route = createFileRoute("/_app/gyms/$gymId/finance/")({
  component: () => {
    const { gymId } = Route.useParams()
    return <FinanceOverviewPage gymId={gymId} />
  },
})
