import { ChevronDown, ChevronUp, Copy, Plus, Trash2 } from "lucide-react"
import { type InputHTMLAttributes, useId, useState } from "react"
import { translateApiError } from "@/api"
import type {
  DayInput,
  ExerciseInput,
  ExercisePublic,
  SetInput,
} from "@/client"
import {
  Button,
  ErrorState,
  IconButton,
  SearchableSelectField,
  TextField,
} from "@/components/M3"
import { type TranslationKey, useI18n } from "@/i18n"
import { useExerciseCategories } from "@/lib/useExerciseCategories"

// Table column headings provide the visible labels; each control also has an
// explicitly associated HTML label for keyboard and assistive-technology users.
function SetField({
  label,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId()
  return (
    <>
      <label className="sr-only" htmlFor={id}>
        {label}
      </label>
      <input {...props} id={id} />
    </>
  )
}

function moveItem<T>(items: T[], index: number, delta: number): T[] {
  const next = [...items]
  const target = index + delta
  if (target < 0 || target >= next.length) return items
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function toNumber(value: string): number | null {
  if (value.trim() === "") return null
  const number = Number(value)
  return Number.isNaN(number) ? null : number
}

const WEEKDAY_ORDER = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"] as const
const UNKNOWN_WEEKDAY_RANK = WEEKDAY_ORDER.length

function weekdayRank(weekday: string | null | undefined): number {
  const index = WEEKDAY_ORDER.indexOf(weekday as (typeof WEEKDAY_ORDER)[number])
  return index === -1 ? UNKNOWN_WEEKDAY_RANK : index
}

function defaultValueSet(setNumber: number): SetInput {
  return {
    set_number: setNumber,
    reps_min: 8,
    reps_max: 12,
    weight_kg: null,
    intensity: null,
    rest_seconds: 60,
    duration_seconds: null,
    note: null,
  }
}

function defaultValueExercise(exercise: ExercisePublic): ExerciseInput {
  return {
    exercise_id: exercise.id,
    order_index: 0,
    notes: null,
    sets: [defaultValueSet(1)],
  }
}

export function ProgramStructureEditor({
  days,
  onChange,
  exerciseOptions,
  trainedDaysCount,
  readOnly = false,
}: {
  days: DayInput[]
  onChange: (days: DayInput[]) => void
  exerciseOptions: ExercisePublic[]
  trainedDaysCount?: number | null
  readOnly?: boolean
}) {
  const { t, direction, formatNumber } = useI18n()
  const categoriesQuery = useExerciseCategories()
  const categories = categoriesQuery.data ?? []
  const [categoryErrors, setCategoryErrors] = useState<Record<number, string>>(
    {},
  )
  const [activeTabIndex, setActiveTabIndex] = useState(0)

  const dayLimit = trainedDaysCount ?? null
  // Weekday-bound days are shown in the athlete's chronological week order;
  // legacy/unassigned days keep their original order after them.
  const shownTabs = days
    .map((day, index) => ({ day, index }))
    .sort(
      (a, b) =>
        weekdayRank(a.day.weekday) - weekdayRank(b.day.weekday) ||
        a.index - b.index,
    )
  const activeEntry =
    shownTabs[Math.max(0, Math.min(activeTabIndex, shownTabs.length - 1))]

  function updateDay(index: number, patch: Partial<DayInput>) {
    setCategoryErrors((previous) => ({ ...previous, [index]: "" }))
    onChange(
      days.map((day, dayIndex) =>
        dayIndex === index ? { ...day, ...patch } : day,
      ),
    )
  }

  function selectedCategories(day: DayInput): string[] {
    return day.category_ids?.length
      ? day.category_ids
      : day.category_id
        ? [day.category_id]
        : []
  }

  function toggleDayCategory(index: number, categoryId: string) {
    const day = days[index]
    const current = selectedCategories(day)
    let next = current.includes(categoryId)
      ? current.filter((id) => id !== categoryId)
      : [...current, categoryId]
    if (!current.length) {
      next = [
        ...new Set([
          ...next,
          ...day.exercises.flatMap((item) => {
            const entry = exerciseOptions.find(
              (exercise) => exercise.id === item.exercise_id,
            )
            return entry ? [entry.category_id] : []
          }),
        ]),
      ]
    }
    if (
      current.includes(categoryId) &&
      day.exercises.some(
        (item) =>
          exerciseOptions.find((exercise) => exercise.id === item.exercise_id)
            ?.category_id === categoryId,
      )
    ) {
      setCategoryErrors((previous) => ({
        ...previous,
        [index]: t("program.categoryConflict"),
      }))
      return
    }
    updateDay(index, {
      category_ids: next,
      category_id: next.length === 1 ? next[0] : null,
    })
  }

  function updateExercise(
    dayIndex: number,
    exerciseIndex: number,
    patch: Partial<ExerciseInput>,
  ) {
    const day = days[dayIndex]
    if (!day) return
    const exercises = day.exercises.map((exercise, index) =>
      index === exerciseIndex ? { ...exercise, ...patch } : exercise,
    )
    updateDay(dayIndex, { exercises })
  }

  function updateSet(
    dayIndex: number,
    exerciseIndex: number,
    setIndex: number,
    patch: Partial<SetInput>,
  ) {
    const target = days[dayIndex]?.exercises[exerciseIndex]
    if (!target) return
    const sets = target.sets.map((set, index) =>
      index === setIndex ? { ...set, ...patch } : set,
    )
    updateExercise(dayIndex, exerciseIndex, { sets })
  }

  function addDay() {
    if (dayLimit !== null && days.length >= dayLimit) return
    const nextDays = [
      ...days,
      {
        day_number: days.length + 1,
        title: `${t("program.day")} ${days.length + 1}`,
        notes: null,
        category_id: null,
        category_ids: [],
        exercises: [],
      },
    ]
    onChange(nextDays)
    setActiveTabIndex(nextDays.length - 1)
  }

  function duplicateDay(index: number) {
    if (dayLimit !== null && days.length >= dayLimit) return
    const copy = clone(days[index])
    copy.title = `${copy.title} (${t("program.duplicateDay")})`
    copy.weekday = null
    const next = [...days]
    next.splice(index + 1, 0, copy)
    onChange(next)
    setActiveTabIndex(index + 1)
  }

  function addExercise(dayIndex: number, exerciseId: string) {
    const exercise = exerciseOptions.find((item) => item.id === exerciseId)
    if (!exercise) return
    const day = days[dayIndex]
    const nextExercise = defaultValueExercise(exercise)
    nextExercise.order_index = day.exercises.length
    updateDay(dayIndex, { exercises: [...day.exercises, nextExercise] })
  }

  function duplicateExercise(dayIndex: number, exerciseIndex: number) {
    const day = days[dayIndex]
    const copy = clone(day.exercises[exerciseIndex])
    copy.sets = copy.sets.map((set, index) => ({
      ...set,
      set_number: index + 1,
    }))
    const exercises = [...day.exercises]
    exercises.splice(exerciseIndex + 1, 0, copy)
    updateDay(dayIndex, { exercises })
  }

  function addSet(dayIndex: number, exerciseIndex: number) {
    const exercise = days[dayIndex]?.exercises[exerciseIndex]
    if (!exercise) return
    const sets = [...exercise.sets, defaultValueSet(exercise.sets.length + 1)]
    updateExercise(dayIndex, exerciseIndex, { sets })
  }

  function duplicateSet(
    dayIndex: number,
    exerciseIndex: number,
    setIndex: number,
  ) {
    const exercise = days[dayIndex]?.exercises[exerciseIndex]
    if (!exercise) return
    const copy = clone(exercise.sets[setIndex])
    const sets = [...exercise.sets]
    sets.splice(setIndex + 1, 0, copy)
    updateExercise(dayIndex, exerciseIndex, {
      sets: sets.map((set, index) => ({ ...set, set_number: index + 1 })),
    })
  }

  function removeSet(
    dayIndex: number,
    exerciseIndex: number,
    setIndex: number,
  ) {
    const exercise = days[dayIndex]?.exercises[exerciseIndex]
    if (!exercise) return
    updateExercise(dayIndex, exerciseIndex, {
      sets: exercise.sets
        .filter((_, index) => index !== setIndex)
        .map((set, index) => ({ ...set, set_number: index + 1 })),
    })
  }

  function renderActiveDay() {
    if (!activeEntry) return null
    const { day, index: dayIndex } = activeEntry
    const chronological = weekdayRank(day.weekday) !== UNKNOWN_WEEKDAY_RANK
    return (
      <section
        className="m3-day program-day-sheet"
        id={`workout-day-${dayIndex}`}
        role="tabpanel"
        aria-labelledby={`workout-day-tab-${dayIndex}`}
      >
        <header className="program-day-sheet__header">
          <div className="program-day-sheet__identity">
            <span className="program-day-sheet__number">
              {formatNumber(day.day_number ?? dayIndex + 1)}
            </span>
            <div className="program-day-sheet__title">
              <span className="program-day-sheet__eyebrow">
                {day.weekday
                  ? t(`weekday.${day.weekday}` as TranslationKey)
                  : t("program.day")}
              </span>
              <TextField
                label={t("program.dayTitle")}
                containerClassName="m3-day-title-field"
                value={day.title}
                onChange={(event) =>
                  updateDay(dayIndex, { title: event.target.value })
                }
                disabled={readOnly}
              />
            </div>
          </div>
          {!readOnly ? (
            <div className="program-day-sheet__tools">
              {!chronological ? (
                <>
                  <IconButton
                    label={t("program.moveUp")}
                    onClick={() => onChange(moveItem(days, dayIndex, -1))}
                    disabled={dayIndex === 0}
                  >
                    <ChevronUp size={18} />
                  </IconButton>
                  <IconButton
                    label={t("program.moveDown")}
                    onClick={() => onChange(moveItem(days, dayIndex, 1))}
                    disabled={dayIndex === days.length - 1}
                  >
                    <ChevronDown size={18} />
                  </IconButton>
                </>
              ) : null}
              {!chronological ? (
                <IconButton
                  label={t("program.duplicateDay")}
                  onClick={() => duplicateDay(dayIndex)}
                  disabled={dayLimit !== null && days.length >= dayLimit}
                >
                  <Copy size={17} />
                </IconButton>
              ) : null}
              <IconButton
                label={t("program.removeDay")}
                onClick={() => {
                  const nextDays = days.filter((_, index) => index !== dayIndex)
                  onChange(nextDays)
                  setActiveTabIndex((previous) =>
                    Math.max(0, Math.min(previous, nextDays.length - 1)),
                  )
                }}
              >
                <Trash2 size={17} />
              </IconButton>
            </div>
          ) : null}
        </header>
        <div className="m3-day__body">
          <fieldset
            className="m3-category-picker"
            disabled={
              readOnly || categoriesQuery.isPending || categoriesQuery.isError
            }
          >
            <legend>{t("program.dayCategories")}</legend>
            <p className="muted">{t("program.categoryHelp")}</p>
            <div className="m3-category-picker__options">
              {categories.map((category) => (
                <label key={category.id} className="m3-category-chip">
                  <input
                    type="checkbox"
                    checked={selectedCategories(day).includes(category.id)}
                    onChange={() => toggleDayCategory(dayIndex, category.id)}
                  />
                  <span>{category.name}</span>
                </label>
              ))}
            </div>
            {categoryErrors[dayIndex] ? (
              <p className="m3-field__error" role="alert">
                {categoryErrors[dayIndex]}
              </p>
            ) : null}
          </fieldset>
          <p className="m3-day-summary">
            {t("program.daySummary", {
              exercises: formatNumber(day.exercises.length),
              sets: formatNumber(
                day.exercises.reduce(
                  (total, exercise) => total + exercise.sets.length,
                  0,
                ),
              ),
            })}
          </p>
          <TextField
            label={t("program.dayNotes")}
            value={day.notes ?? ""}
            onChange={(event) =>
              updateDay(dayIndex, { notes: event.target.value || null })
            }
            multiline
            rows={2}
            disabled={readOnly}
          />

          {day.exercises.length === 0 ? (
            <p className="muted" style={{ fontSize: 12 }}>
              {t("program.noExercises")}
            </p>
          ) : null}

          {day.exercises.map((exercise, exerciseIndex) => {
            const libraryEntry = exerciseOptions.find(
              (item) => item.id === exercise.exercise_id,
            )
            return (
              <article
                className="m3-exercise-block program-exercise"
                key={`${exercise.exercise_id}-${exerciseIndex}`}
              >
                <div className="program-exercise__head">
                  <span className="program-exercise__order" aria-hidden>
                    {formatNumber(exerciseIndex + 1)}
                  </span>
                  <div className="program-exercise__identity">
                    <SearchableSelectField
                      label={t("program.exercise")}
                      value={exercise.exercise_id}
                      onChange={(value) =>
                        updateExercise(dayIndex, exerciseIndex, {
                          exercise_id: value,
                        })
                      }
                      options={exerciseOptions
                        .filter(
                          (item) =>
                            !selectedCategories(day).length ||
                            selectedCategories(day).includes(
                              item.category_id,
                            ) ||
                            item.id === exercise.exercise_id,
                        )
                        .map((item) => ({
                          value: item.id,
                          label: `${item.name_fa} · ${item.muscle_group}`,
                        }))}
                      disabled={readOnly}
                    />
                    {libraryEntry ? (
                      <div className="program-exercise__meta">
                        <span className="program-exercise__chip">
                          {libraryEntry.muscle_group}
                        </span>
                        <span className="muted">
                          {t("program.muscleGroup")}
                        </span>
                      </div>
                    ) : null}
                  </div>
                  {!readOnly ? (
                    <div className="program-exercise__tools">
                      <IconButton
                        label={t("program.moveUp")}
                        onClick={() => {
                          const exercises = moveItem(
                            day.exercises,
                            exerciseIndex,
                            -1,
                          )
                          updateDay(dayIndex, { exercises })
                        }}
                        disabled={exerciseIndex === 0}
                      >
                        <ChevronUp size={17} />
                      </IconButton>
                      <IconButton
                        label={t("program.moveDown")}
                        onClick={() => {
                          const exercises = moveItem(
                            day.exercises,
                            exerciseIndex,
                            1,
                          )
                          updateDay(dayIndex, { exercises })
                        }}
                        disabled={exerciseIndex === day.exercises.length - 1}
                      >
                        <ChevronDown size={17} />
                      </IconButton>
                      <IconButton
                        label={t("program.duplicateExercise")}
                        onClick={() =>
                          duplicateExercise(dayIndex, exerciseIndex)
                        }
                      >
                        <Copy size={16} />
                      </IconButton>
                      <IconButton
                        label={t("program.removeExercise")}
                        onClick={() =>
                          updateDay(dayIndex, {
                            exercises: day.exercises.filter(
                              (_, index) => index !== exerciseIndex,
                            ),
                          })
                        }
                      >
                        <Trash2 size={16} />
                      </IconButton>
                    </div>
                  ) : null}
                </div>

                <TextField
                  label={t("program.exerciseNotes")}
                  value={exercise.notes ?? ""}
                  onChange={(event) =>
                    updateExercise(dayIndex, exerciseIndex, {
                      notes: event.target.value || null,
                    })
                  }
                  disabled={readOnly}
                  containerClassName="program-exercise__notes"
                />

                <div className="m3-set-editor program-set-ledger">
                  <div className="program-set-ledger__head" aria-hidden>
                    <span>{t("program.set")}</span>
                    <span>{t("program.repsMin")}</span>
                    <span>{t("program.repsMax")}</span>
                    <span>
                      {t("program.weight")} ({t("common.units.kg")})
                    </span>
                    <span>{t("program.intensity")}</span>
                    <span>
                      {t("program.rest")} ({t("common.units.seconds")})
                    </span>
                    <span>
                      {t("program.duration")} ({t("common.units.seconds")})
                    </span>
                    <span>{t("program.setNote")}</span>
                    <span>{t("common.actions")}</span>
                  </div>
                  {exercise.sets.map((set, setIndex) => (
                    <fieldset
                      className="program-set-row"
                      aria-label={`${t("program.set")} ${formatNumber(
                        setIndex + 1,
                      )}`}
                      key={`${set.set_number}-${setIndex}`}
                    >
                      <span className="program-set-row__number" aria-hidden>
                        {formatNumber(setIndex + 1)}
                      </span>
                      <div
                        className="program-set-field"
                        data-label={t("program.repsMin")}
                      >
                        <SetField
                          type="number"
                          inputMode="numeric"
                          min={0}
                          value={set.reps_min ?? ""}
                          label={t("program.repsMin")}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateSet(dayIndex, exerciseIndex, setIndex, {
                              reps_min: toNumber(event.target.value),
                            })
                          }
                        />
                      </div>
                      <div
                        className="program-set-field"
                        data-label={t("program.repsMax")}
                      >
                        <SetField
                          type="number"
                          inputMode="numeric"
                          min={0}
                          value={set.reps_max ?? ""}
                          label={t("program.repsMax")}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateSet(dayIndex, exerciseIndex, setIndex, {
                              reps_max: toNumber(event.target.value),
                            })
                          }
                        />
                      </div>
                      <div
                        className="program-set-field"
                        data-label={`${t("program.weight")} (${t(
                          "common.units.kg",
                        )})`}
                      >
                        <SetField
                          type="number"
                          min={0}
                          step="0.5"
                          inputMode="decimal"
                          value={set.weight_kg ?? ""}
                          label={t("program.weight")}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateSet(dayIndex, exerciseIndex, setIndex, {
                              weight_kg: toNumber(event.target.value),
                            })
                          }
                        />
                      </div>
                      <div
                        className="program-set-field"
                        data-label={t("program.intensity")}
                      >
                        <SetField
                          type="text"
                          value={set.intensity ?? ""}
                          label={t("program.intensity")}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateSet(dayIndex, exerciseIndex, setIndex, {
                              intensity: event.target.value || null,
                            })
                          }
                        />
                      </div>
                      <div
                        className="program-set-field"
                        data-label={`${t("program.rest")} (${t(
                          "common.units.seconds",
                        )})`}
                      >
                        <SetField
                          type="number"
                          inputMode="numeric"
                          min={0}
                          value={set.rest_seconds ?? ""}
                          label={t("program.rest")}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateSet(dayIndex, exerciseIndex, setIndex, {
                              rest_seconds: toNumber(event.target.value),
                            })
                          }
                        />
                      </div>
                      <div
                        className="program-set-field"
                        data-label={`${t("program.duration")} (${t(
                          "common.units.seconds",
                        )})`}
                      >
                        <SetField
                          type="number"
                          inputMode="numeric"
                          min={0}
                          value={set.duration_seconds ?? ""}
                          label={t("program.duration")}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateSet(dayIndex, exerciseIndex, setIndex, {
                              duration_seconds: toNumber(event.target.value),
                            })
                          }
                        />
                      </div>
                      <div
                        className="program-set-field"
                        data-label={t("program.setNote")}
                      >
                        <SetField
                          type="text"
                          value={set.note ?? ""}
                          label={t("program.setNote")}
                          disabled={readOnly}
                          onChange={(event) =>
                            updateSet(dayIndex, exerciseIndex, setIndex, {
                              note: event.target.value || null,
                            })
                          }
                        />
                      </div>
                      <div className="program-set-row__actions">
                        {!readOnly ? (
                          <>
                            <IconButton
                              label={t("program.duplicateSet")}
                              onClick={() =>
                                duplicateSet(dayIndex, exerciseIndex, setIndex)
                              }
                            >
                              <Copy size={14} />
                            </IconButton>
                            <IconButton
                              label={t("program.removeSet")}
                              onClick={() =>
                                removeSet(dayIndex, exerciseIndex, setIndex)
                              }
                            >
                              <Trash2 size={14} />
                            </IconButton>
                          </>
                        ) : null}
                      </div>
                    </fieldset>
                  ))}
                  {exercise.sets.length === 0 ? (
                    <p className="program-set-ledger__empty">
                      {t("program.noSets")}
                    </p>
                  ) : null}
                </div>

                {!readOnly ? (
                  <Button
                    variant="outlined"
                    size="sm"
                    className="program-add-set"
                    icon={<Plus size={14} />}
                    onClick={() => addSet(dayIndex, exerciseIndex)}
                  >
                    {t("program.addSet")}
                  </Button>
                ) : null}
              </article>
            )
          })}

          {!readOnly ? (
            <AddExercise
              key={selectedCategories(day).join(",")}
              categoryIds={selectedCategories(day)}
              exerciseOptions={exerciseOptions}
              onAdd={(exerciseId) => addExercise(dayIndex, exerciseId)}
            />
          ) : null}
        </div>
      </section>
    )
  }

  return (
    <div className="program-authoring">
      {categoriesQuery.isError ? (
        <ErrorState
          message={translateApiError(categoriesQuery.error, t)}
          onRetry={() => categoriesQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : null}

      <aside className="program-day-rail" aria-label={t("program.days")}>
        <div className="program-day-rail__head">
          <div>
            <span className="program-day-rail__eyebrow">
              {t("program.structure")}
            </span>
            <strong>{t("program.days")}</strong>
          </div>
          <span className="program-day-rail__count">
            {formatNumber(days.length)}
          </span>
        </div>

        {days.length === 0 ? (
          <p className="program-day-rail__empty">{t("program.noDays")}</p>
        ) : (
          <div
            className="program-day-tabs"
            role="tablist"
            aria-label={t("program.days")}
            onKeyDown={(event) => {
              const keys = ["ArrowLeft", "ArrowRight", "Home", "End"]
              if (!keys.includes(event.key)) return
              const buttons = Array.from(
                event.currentTarget.querySelectorAll<HTMLButtonElement>(
                  '[role="tab"]',
                ),
              )
              const current = buttons.indexOf(
                document.activeElement as HTMLButtonElement,
              )
              let next = current
              if (event.key === "Home") next = 0
              else if (event.key === "End") next = buttons.length - 1
              else if (event.key === "ArrowLeft") {
                next = direction === "rtl" ? current + 1 : current - 1
              } else {
                next = direction === "rtl" ? current - 1 : current + 1
              }
              if (next < 0 || next >= buttons.length) return
              event.preventDefault()
              buttons[next].focus()
              setActiveTabIndex(next)
            }}
          >
            {shownTabs.map((entry, tabIndex) => {
              const active = tabIndex === activeTabIndex
              const setCount = entry.day.exercises.reduce(
                (total, exercise) => total + exercise.sets.length,
                0,
              )
              return (
                <button
                  key={entry.index}
                  type="button"
                  role="tab"
                  id={`workout-day-tab-${entry.index}`}
                  aria-selected={active}
                  aria-controls={`workout-day-${entry.index}`}
                  tabIndex={active ? 0 : -1}
                  className={`program-day-tab ${active ? "is-active" : ""}`}
                  onClick={() => setActiveTabIndex(tabIndex)}
                >
                  <span className="program-day-tab__number">
                    {formatNumber(entry.day.day_number ?? tabIndex + 1)}
                  </span>
                  <span className="program-day-tab__body">
                    <span className="program-day-tab__title">
                      {entry.day.weekday
                        ? t(`weekday.${entry.day.weekday}` as TranslationKey)
                        : entry.day.title}
                    </span>
                    <span className="program-day-tab__meta">
                      {formatNumber(entry.day.exercises.length)}{" "}
                      {t("program.metricExercises")} · {formatNumber(setCount)}{" "}
                      {t("program.metricSets")}
                    </span>
                  </span>
                </button>
              )
            })}
          </div>
        )}

        {!readOnly &&
        days.length > 0 &&
        (dayLimit === null || days.length < dayLimit) ? (
          <Button
            variant="outlined"
            className="program-day-rail__add"
            icon={<Plus size={16} />}
            onClick={addDay}
          >
            {t("program.addDay")}
          </Button>
        ) : null}

        {dayLimit !== null ? (
          <p className="program-day-rail__limit">
            {formatNumber(days.length)} / {formatNumber(dayLimit)}
          </p>
        ) : null}
      </aside>

      <div className="program-day-stage">
        {days.length === 0 ? (
          <div className="program-empty-state">
            <span className="program-empty-state__icon" aria-hidden>
              <Plus size={22} />
            </span>
            <h3>{t("program.noDays")}</h3>
            <p className="muted">{t("program.draftBanner")}</p>
            {!readOnly && (dayLimit === null || days.length < dayLimit) ? (
              <Button icon={<Plus size={16} />} onClick={addDay}>
                {t("program.addDay")}
              </Button>
            ) : null}
          </div>
        ) : (
          renderActiveDay()
        )}
      </div>
    </div>
  )
}

function AddExercise({
  exerciseOptions,
  categoryIds,
  onAdd,
}: {
  exerciseOptions: ExercisePublic[]
  categoryIds: string[]
  onAdd: (exerciseId: string) => void
}) {
  const { t } = useI18n()
  const [selected, setSelected] = useState("")
  const availableExercises = exerciseOptions.filter(
    (item) => !categoryIds.length || categoryIds.includes(item.category_id),
  )

  return (
    <div className="m3-builder-add-exercise">
      <SearchableSelectField
        label={t("program.addExercise")}
        value={selected}
        onChange={setSelected}
        options={availableExercises.map((item) => ({
          value: item.id,
          label: `${item.name_fa} · ${item.muscle_group}`,
        }))}
        placeholder={t("program.chooseExercise")}
        helper={
          categoryIds.length > 0 && !availableExercises.length
            ? t("program.emptyCategory")
            : undefined
        }
      />
      <Button
        icon={<Plus size={15} />}
        disabled={!selected}
        onClick={() => {
          onAdd(selected)
          setSelected("")
        }}
      >
        {t("common.add")}
      </Button>
    </div>
  )
}
