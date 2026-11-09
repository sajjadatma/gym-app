import { createFileRoute } from "@tanstack/react-router"

import { FinanceOverviewPage } from "@/pages/finance/FinanceOverviewPage"

export const Route = createFileRoute("/_app/finance/")({
  component: () => <FinanceOverviewPage />,
})
