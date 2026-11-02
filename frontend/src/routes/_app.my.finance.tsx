import { createFileRoute } from "@tanstack/react-router"

import { ClubRedirect } from "@/components/ClubRedirect"

export const Route = createFileRoute("/_app/my/finance")({
  component: () => <ClubRedirect to="/gyms/$gymId/my/finance" />,
})
