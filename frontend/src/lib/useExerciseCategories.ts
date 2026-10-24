import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/auth"
import { ExerciseCategoriesService } from "@/client"

export function useExerciseCategories() {
  const { activeGymId } = useAuth()
  return useQuery({
    queryKey: ["exercise-categories", activeGymId],
    queryFn: async () =>
      (await ExerciseCategoriesService.listExerciseCategories()).data.data,
    enabled: Boolean(activeGymId),
  })
}
