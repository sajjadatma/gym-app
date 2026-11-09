import { createFileRoute } from "@tanstack/react-router"

import { FinanceContractsPage } from "@/pages/finance/FinanceContractsPage"

export const Route = createFileRoute("/_app/gyms/$gymId/finance/contracts")({
  component: () => {
    const { gymId } = Route.useParams()
    return <FinanceContractsPage gymId={gymId} />
  },
})
