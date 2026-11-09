import { createFileRoute } from "@tanstack/react-router"

import { FinanceSalesPage } from "@/pages/finance/FinanceSalesPage"

export const Route = createFileRoute("/_app/gyms/$gymId/finance/sales")({
  component: () => {
    const { gymId } = Route.useParams()
    return <FinanceSalesPage gymId={gymId} />
  },
})
