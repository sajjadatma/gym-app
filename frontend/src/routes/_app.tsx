import { createFileRoute, redirect } from "@tanstack/react-router"

import { AppShell } from "@/components/AppShell"

export const Route = createFileRoute("/_app")({
  beforeLoad: () => {
    if (!localStorage.getItem("access_token")) {
      throw redirect({ to: "/login" })
    }
  },
  component: AppShell,
})
