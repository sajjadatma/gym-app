import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

export const Route = createFileRoute("/_app/members")({
  component: () => <ClubRedirect to="/gyms/$gymId/members" />,
})
