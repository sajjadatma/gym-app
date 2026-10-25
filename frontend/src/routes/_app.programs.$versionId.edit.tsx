import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

function Page() {
  const { versionId } = Route.useParams()
  return (
    <ClubRedirect
      to="/gyms/$gymId/programs/$versionId/edit"
      params={{ versionId }}
    />
  )
}

export const Route = createFileRoute("/_app/programs/$versionId/edit")({
  component: Page,
})
