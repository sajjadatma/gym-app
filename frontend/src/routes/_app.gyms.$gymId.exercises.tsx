import { createFileRoute } from "@tanstack/react-router"

import { ExercisesPage } from "@/pages/ExercisesPage"

export const Route = createFileRoute("/_app/gyms/$gymId/exercises")({
  component: ExercisesPage,
})
