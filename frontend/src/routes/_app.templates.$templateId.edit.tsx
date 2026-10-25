import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

function Page() {
  const { templateId } = Route.useParams()
  return (
    <ClubRedirect
      to="/gyms/$gymId/templates/$templateId/edit"
      params={{ templateId }}
    />
  )
}

export const Route = createFileRoute("/_app/templates/$templateId/edit")({
  component: Page,
})
