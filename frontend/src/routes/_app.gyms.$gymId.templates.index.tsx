import { createFileRoute } from "@tanstack/react-router"

import { TemplatesPage } from "@/pages/TemplatesPage"

export const Route = createFileRoute("/_app/gyms/$gymId/templates/")({
  component: TemplatesPage,
})
