import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

export const Route = createFileRoute("/_app/my/earnings")({
  component: () => <ClubRedirect to="/gyms/$gymId/my/earnings" />,
})
