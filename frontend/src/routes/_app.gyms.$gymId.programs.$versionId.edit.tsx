import { createFileRoute } from "@tanstack/react-router"

import { ProgramEditorPage } from "@/pages/ProgramEditorPage"

function Page() {
  const { versionId } = Route.useParams()
  return <ProgramEditorPage key={versionId} versionId={versionId} />
}

export const Route = createFileRoute(
  "/_app/gyms/$gymId/programs/$versionId/edit",
)({
  component: Page,
})
