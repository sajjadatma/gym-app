import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

export const Route = createFileRoute("/_app/exercises")({
  component: () => <ClubRedirect to="/gyms/$gymId/exercises" />,
})
