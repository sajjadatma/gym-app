import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_app/gyms/$gymId/templates")({
  component: Outlet,
})
