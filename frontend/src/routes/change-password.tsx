import { createFileRoute } from "@tanstack/react-router"

import { ChangePasswordPage } from "@/pages/ChangePasswordPage"

export const Route = createFileRoute("/change-password")({
  component: ChangePasswordPage,
})
