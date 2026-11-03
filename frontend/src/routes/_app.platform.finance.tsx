import { createFileRoute } from "@tanstack/react-router"

import { PlatformFinancePage } from "@/pages/PlatformFinancePage"

export const Route = createFileRoute("/_app/platform/finance")({
  component: PlatformFinancePage,
})
