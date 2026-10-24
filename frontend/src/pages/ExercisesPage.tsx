import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Dumbbell, Pencil, Plus, Search } from "lucide-react"
import { useDeferredValue, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  ExerciseCategoriesService,
  type ExercisePublic,
  ExercisesService,
} from "@/client"
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useExerciseCategories } from "@/lib/useExerciseCategories"
import { useSnackbar } from "@/snackbar"

export function ExercisesPage() {
  const { t } = useI18n()
  const { activeGym, activeGymId, isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)
  const [group, setGroup] = useState("")
  const categoriesQuery = useExerciseCategories()
  const [categoryOpen, setCategoryOpen] = useState(false)
  const [categoryName, setCategoryName] = useState("")
  const [categoryError, setCategoryError] = useState<string | null>(null)
  const [creatingCategory, setCreatingCategory] = useState(false)
  const [open, setOpen] = useState(false)
  const [editExercise, setEditExercise] = useState<ExercisePublic | null>(null)
  const [form, setForm] = useState({
    name_fa: "",
    category_id: "",
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

  const canEdit = isAdmin
  const exercises = (exercisesQuery.data ?? []).filter(
    (exercise) => !group || exercise.category_id === group,
  )
  const categories = categoriesQuery.data ?? []

  async function saveCategory() {
    if (!categoryName.trim()) {
      setCategoryError(t("validation.required"))
      return
    }
    setCategoryError(null)
    setCreatingCategory(true)
    try {
      const { data } = await ExerciseCategoriesService.createExerciseCategory({
        body: { name: categoryName.trim() },
      })
      await queryClient.invalidateQueries({
        queryKey: ["exercise-categories", activeGymId],
      })
      setGroup(data.id)
      setCategoryOpen(false)
      show(t("categories.created"), "success")
    } catch (error) {
      setCategoryError(translateApiError(error, t))
    } finally {
      setCreatingCategory(false)
    }
  }

  function openCreate() {
    setError(null)
    setEditExercise(null)
    setForm({
      name_fa: "",
      category_id: group,
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
      category_id: exercise.category_id,
      description: exercise.description ?? "",
      instructions: exercise.instructions ?? "",
    })
    setOpen(true)
  }

  async function save() {
    setError(null)
    if (!form.name_fa.trim() || !form.category_id) {
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
            category_id: form.category_id,
            description: form.description || null,
            instructions: form.instructions || null,
          },
        })
        show(t("exercises.updated"), "success")
      } else {
        await ExercisesService.createExercise({
          body: {
            name_fa: form.name_fa,
            category_id: form.category_id,
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
            <>
              <Button
                variant="outlined"
                icon={<Plus size={17} />}
                onClick={() => {
                  setCategoryName("")
                  setCategoryError(null)
                  setCategoryOpen(true)
                }}
              >
                {t("categories.add")}
              </Button>
              <Button
                icon={<Plus size={17} />}
                onClick={openCreate}
                disabled={categoriesQuery.isPending || categoriesQuery.isError}
              >
                {t("exercises.add")}
              </Button>
            </>
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
        <SelectField
          label={t("categories.category")}
          value={group}
          onChange={setGroup}
          disabled={categoriesQuery.isPending || categoriesQuery.isError}
          options={[
            { value: "", label: t("exercises.allGroups") },
            ...categories.map((category) => ({
              value: category.id,
              label: category.name,
            })),
          ]}
        />
      </div>

      {categoriesQuery.isError ? (
        <ErrorState
          message={translateApiError(categoriesQuery.error, t)}
          onRetry={() => categoriesQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : null}
      {!canEdit ? (
        <p className="muted m3-catalog-hint">{t("categories.coachReadOnly")}</p>
      ) : null}
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
              canEdit && exercise.is_custom && exercise.gym_id === activeGymId
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
          <SelectField
            label={t("categories.category")}
            value={form.category_id}
            onChange={(category_id) => setForm({ ...form, category_id })}
            options={categories.map((category) => ({
              value: category.id,
              label: category.name,
            }))}
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
      <Dialog
        open={categoryOpen}
        title={t("categories.add")}
        onClose={() => setCategoryOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setCategoryOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={saveCategory} loading={creatingCategory}>
              {t("common.create")}
            </Button>
          </>
        }
      >
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault()
            void saveCategory()
          }}
        >
          <TextField
            label={t("categories.name")}
            value={categoryName}
            maxLength={100}
            required
            onChange={(event) => setCategoryName(event.target.value)}
            error={categoryError ?? undefined}
            helper={t("categories.gymScope")}
          />
        </form>
      </Dialog>
    </>
  )
}
