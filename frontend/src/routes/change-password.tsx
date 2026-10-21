import { createFileRoute, redirect } from "@tanstack/react-router"

import { ChangePasswordPage } from "@/pages/ChangePasswordPage"

export const Route = createFileRoute("/change-password")({
  beforeLoad: () => {
    if (!localStorage.getItem("access_token")) {
      throw redirect({ to: "/login" })
    }
  },
  component: ChangePasswordPage,
})
