import { createFileRoute } from "@tanstack/react-router"

import { FinanceSettlementsPage } from "@/pages/finance/FinanceSettlementsPage"

export const Route = createFileRoute("/_app/gyms/$gymId/finance/settlements")({
  component: () => {
    const { gymId } = Route.useParams()
    return <FinanceSettlementsPage gymId={gymId} />
  },
})
