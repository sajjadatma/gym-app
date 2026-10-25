import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

export const Route = createFileRoute("/_app/my/profile")({
  component: () => <ClubRedirect to="/gyms/$gymId/my/profile" />,
})
