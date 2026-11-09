import { createFileRoute } from "@tanstack/react-router"

import { FinanceReportsPage } from "@/pages/finance/FinanceReportsPage"

export const Route = createFileRoute("/_app/finance/reports")({
  component: () => <FinanceReportsPage />,
})
