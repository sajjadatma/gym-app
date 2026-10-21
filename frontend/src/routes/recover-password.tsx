import { createFileRoute } from "@tanstack/react-router"

import { RecoverPasswordPage } from "@/pages/RecoverPasswordPage"

export const Route = createFileRoute("/recover-password")({
  component: RecoverPasswordPage,
})
