import { createFileRoute } from "@tanstack/react-router"

import { TemplateEditorPage } from "@/pages/TemplateEditorPage"

export const Route = createFileRoute("/_app/gyms/$gymId/templates/new")({
  component: TemplateEditorPage,
})
