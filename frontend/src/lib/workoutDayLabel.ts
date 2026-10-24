import type { DayPublic } from "@/client"

/** Render saved categories, with a fallback for legacy mixed days. */
export function workoutDayLabel(
  day: DayPublic,
  dayWord: string,
  number: string,
) {
  const categories = day.category_names?.length
    ? day.category_names
    : day.category_name
      ? [day.category_name]
      : [...new Set(day.exercises.map((exercise) => exercise.muscle_group))]
  const category = categories.join(" / ")
  const defaultTitle = /^(روز|Day)\s*[0-9۰-۹٠-٩]+$/.test(day.title.trim())
  const title =
    defaultTitle || categories.includes(day.title.trim()) ? "" : day.title
  const details = [
    title,
    category && !title.includes(category) ? category : "",
  ].filter(Boolean)
  return `${dayWord} ${number}${details.length ? ` — ${details.join(" · ")}` : ""}`
}
