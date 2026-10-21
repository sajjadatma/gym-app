import { createFileRoute } from "@tanstack/react-router"

import { GymsPage } from "@/pages/GymsPage"

export const Route = createFileRoute("/_app/gyms/")({
  component: GymsPage,
})
