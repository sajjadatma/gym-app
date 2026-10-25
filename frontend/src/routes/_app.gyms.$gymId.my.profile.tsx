import { createFileRoute } from "@tanstack/react-router"

import { MyProfilePage } from "@/pages/MyProfilePage"

export const Route = createFileRoute("/_app/gyms/$gymId/my/profile")({
  component: MyProfilePage,
})
