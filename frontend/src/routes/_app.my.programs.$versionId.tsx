import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

function Page() {
  const { versionId } = Route.useParams()
  return (
    <ClubRedirect
      to="/gyms/$gymId/my/programs/$versionId"
      params={{ versionId }}
    />
  )
}

export const Route = createFileRoute("/_app/my/programs/$versionId")({
  component: Page,
})
