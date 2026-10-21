import { createFileRoute } from "@tanstack/react-router"

import { AcceptInvitationPage } from "@/pages/AcceptInvitationPage"

export const Route = createFileRoute("/accept-invitation")({
  component: AcceptInvitationPage,
})
