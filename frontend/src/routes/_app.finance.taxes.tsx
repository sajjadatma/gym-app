import { createFileRoute } from "@tanstack/react-router"

import { FinanceTaxesPage } from "@/pages/finance/FinanceTaxesPage"

export const Route = createFileRoute("/_app/finance/taxes")({
  component: () => <FinanceTaxesPage />,
})
