import { createFileRoute } from "@tanstack/react-router"

import { MyProgramDetailPage } from "@/pages/MyProgramDetailPage"

function Page() {
  const { versionId } = Route.useParams()
  return <MyProgramDetailPage versionId={versionId} />
}

export const Route = createFileRoute(
  "/_app/gyms/$gymId/my/programs/$versionId",
)({
  component: Page,
})
