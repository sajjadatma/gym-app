import { createFileRoute } from "@tanstack/react-router"

import { FinancePlatformContractsPage } from "@/pages/finance/FinancePlatformContractsPage"

export const Route = createFileRoute("/_app/finance/platform-contracts")({
  component: FinancePlatformContractsPage,
})
