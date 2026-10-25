import { createFileRoute } from "@tanstack/react-router"

import { TemplateEditorPage } from "@/pages/TemplateEditorPage"

function Page() {
  const { templateId } = Route.useParams()
  return <TemplateEditorPage templateId={templateId} />
}

export const Route = createFileRoute(
  "/_app/gyms/$gymId/templates/$templateId/edit",
)({
  component: Page,
})
