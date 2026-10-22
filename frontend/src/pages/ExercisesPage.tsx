import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Dumbbell, Pencil, Plus, Search } from "lucide-react"
import { useDeferredValue, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type ExercisePublic, ExercisesService } from "@/client"
import {
  Button,
  Card,
  Chip,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function ExercisesPage() {
  const { t } = useI18n()
  const { activeGym, activeGymId, activeRole, isSuperuser } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)
  const [group, setGroup] = useState("")
  const [open, setOpen] = useState(false)
  const [editExercise, setEditExercise] = useState<ExercisePublic | null>(null)
  const [form, setForm] = useState({
    name_fa: "",
    muscle_group: "",
    description: "",
    instructions: "",
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const exercisesQuery = useQuery({
    queryKey: ["exercises", activeGymId, deferredSearch],
    queryFn: async () =>
      (
        await ExercisesService.listExercises({
          query: { q: deferredSearch },
        })
      ).data.data,
    enabled: Boolean(activeGymId),
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("exercises.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  const canEdit = activeRole === "GYM_ADMIN" || activeRole === "COACH"
  const exercises = (exercisesQuery.data ?? []).filter(
    (exercise) => !group || exercise.muscle_group === group,
  )
  const groups = Array.from(
    new Set(
      (exercisesQuery.data ?? []).map((exercise) => exercise.muscle_group),
    ),
  )

  function openCreate() {
    setError(null)
    setEditExercise(null)
    setForm({
      name_fa: "",
      muscle_group: "",
      description: "",
      instructions: "",
    })
    setOpen(true)
  }

  function openEdit(exercise: ExercisePublic) {
    setError(null)
    setEditExercise(exercise)
    setForm({
      name_fa: exercise.name_fa,
      muscle_group: exercise.muscle_group,
      description: exercise.description ?? "",
      instructions: exercise.instructions ?? "",
    })
    setOpen(true)
  }

  async function save() {
    setError(null)
    if (!form.name_fa.trim() || !form.muscle_group.trim()) {
      setError(t("validation.required"))
      return
    }
    setSaving(true)
    try {
      if (editExercise) {
        await ExercisesService.updateExercise({
          path: { exercise_id: editExercise.id },
          body: {
            name_fa: form.name_fa,
            muscle_group: form.muscle_group,
            description: form.description || null,
            instructions: form.instructions || null,
          },
        })
        show(t("exercises.updated"), "success")
      } else {
        await ExercisesService.createExercise({
          body: {
            name_fa: form.name_fa,
            muscle_group: form.muscle_group,
            description: form.description || null,
            instructions: form.instructions || null,
          },
        })
        show(t("exercises.created"), "success")
      }
      await queryClient.invalidateQueries({
        queryKey: ["exercises", activeGymId],
      })
      setOpen(false)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t("exercises.title")}
        subtitle={`${activeGym.name} · ${t("exercises.subtitle")}`}
        actions={
          canEdit ? (
            <Button icon={<Plus size={17} />} onClick={openCreate}>
              {t("exercises.add")}
            </Button>
          ) : undefined
        }
      />

      <div className="m3-filter-bar">
        <TextField
          label={t("exercises.search")}
          type="search"
          name="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          leading={<Search size={18} aria-hidden />}
        />
        <Chip selected={!group} onClick={() => setGroup("")}>
          {t("exercises.allGroups")}
        </Chip>
        {groups.map((item) => (
          <Chip
            key={item}
            selected={group === item}
            onClick={() => setGroup(group === item ? "" : item)}
          >
            {item}
          </Chip>
        ))}
      </div>

      {exercisesQuery.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : exercisesQuery.isError ? (
        <ErrorState
          message={translateApiError(exercisesQuery.error, t)}
          onRetry={() => exercisesQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : exercises.length === 0 ? (
        <EmptyState
          icon={<Dumbbell size={26} />}
          title={t("exercises.empty")}
          action={
            canEdit ? (
              <Button icon={<Plus size={17} />} onClick={openCreate}>
                {t("exercises.add")}
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="m3-card-grid">
          {exercises.map((exercise) => {
            const canEditExercise =
              exercise.is_custom &&
              (isSuperuser ||
                activeRole === "GYM_ADMIN" ||
                exercise.gym_id === activeGymId)
            return (
              <Card key={exercise.id} className="m3-card--outlined">
                <div className="m3-entity-card__head">
                  <div>
                    <div className="m3-entity-card__title">
                      {exercise.name_fa}
                    </div>
                    <div className="m3-entity-card__meta">
                      <span>{exercise.muscle_group}</span>
                    </div>
                  </div>
                  <span
                    className={`m3-chip ${exercise.is_custom ? "m3-chip--selected" : ""}`}
                  >
                    {exercise.is_custom
                      ? t("exercises.custom")
                      : t("exercises.global")}
                  </span>
                </div>
                {exercise.description ? (
                  <p className="muted" style={{ fontSize: 12 }}>
                    {exercise.description}
                  </p>
                ) : null}
                {exercise.instructions ? (
                  <p
                    style={{
                      fontSize: 11.5,
                      color: "var(--m3-on-surface-variant)",
                    }}
                  >
                    {exercise.instructions}
                  </p>
                ) : null}
                {canEditExercise ? (
                  <div className="m3-entity-card__footer">
                    <Button
                      variant="text"
                      size="sm"
                      icon={<Pencil size={14} />}
                      onClick={() => openEdit(exercise)}
                    >
                      {t("common.edit")}
                    </Button>
                  </div>
                ) : null}
              </Card>
            )
          })}
        </div>
      )}

      <Dialog
        open={open}
        title={
          editExercise ? t("exercises.editTitle") : t("exercises.addTitle")
        }
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={save} loading={saving}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <TextField
            label={t("exercises.name")}
            value={form.name_fa}
            onChange={(event) =>
              setForm({ ...form, name_fa: event.target.value })
            }
            required
          />
          <TextField
            label={t("exercises.muscleGroup")}
            value={form.muscle_group}
            onChange={(event) =>
              setForm({ ...form, muscle_group: event.target.value })
            }
            required
          />
          <TextField
            label={t("exercises.description")}
            value={form.description}
            onChange={(event) =>
              setForm({ ...form, description: event.target.value })
            }
            multiline
            rows={2}
          />
          <TextField
            label={t("exercises.instructions")}
            value={form.instructions}
            onChange={(event) =>
              setForm({ ...form, instructions: event.target.value })
            }
            multiline
            rows={3}
          />
        </div>
      </Dialog>
    </>
  )
}
