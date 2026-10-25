import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

export const Route = createFileRoute("/_app/templates/new")({
  component: () => <ClubRedirect to="/gyms/$gymId/templates/new" />,
})
