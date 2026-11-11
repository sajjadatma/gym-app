import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import type { ProgramVersionDetail } from "@/client"
import { DateField } from "@/components/DateField"
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  SectionCard,
  Spinner,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import {
  getSessions,
  logSession,
  type SessionInput,
  type SessionSet,
} from "@/lib/activity-api"
import { daysAgoIso, todayIso } from "@/lib/finance-ui"

function actualNumber(
  raw: string,
  max: number,
  integer = false,
): number | null {
  if (!raw.trim()) return null
  const normalized = raw
    .trim()
    .replace(/[۰-۹]/g, (c) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(c)))
    .replace(/[٠-٩]/g, (c) => String("٠١٢٣٤٥٦٧٨٩".indexOf(c)))
    .replace(/٫/g, ".")
  if (!/^\d+(?:\.\d+)?$/.test(normalized)) throw Error("invalid")
  const value = Number(normalized)
  if (
    !Number.isFinite(value) ||
    value < 0 ||
    value > max ||
    (integer && !Number.isInteger(value))
  )
    throw Error("invalid")
  return value
}

export function WorkoutLogger({
  version,
  dayId,
}: {
  version: ProgramVersionDetail
  dayId: string | undefined | null
}) {
  const { activeGymId } = useAuth()
  const { t, formatNumber } = useI18n()
  const cache = useQueryClient()
  const day = version.days.find((item) => item.id === dayId)
  const [open, setOpen] = useState(false),
    [saving, setSaving] = useState(false),
    [error, setError] = useState<string | null>(null)
  const [performedOn, setPerformedOn] = useState(todayIso()),
    [effort, setEffort] = useState(""),
    [note, setNote] = useState(""),
    [completed, setCompleted] = useState(true),
    [key, setKey] = useState("")
  const [actuals, setActuals] = useState<
    Record<string, { reps: string; weight: string; completed: boolean }>
  >({})
  function start() {
    setPerformedOn(todayIso())
    setEffort("")
    setNote("")
    setCompleted(true)
    setActuals({})
    setError(null)
    setKey(crypto.randomUUID())
    setOpen(true)
  }
  function update(
    id: string,
    change: Partial<{ reps: string; weight: string; completed: boolean }>,
  ) {
    setActuals((previous) => ({
      ...previous,
      [id]: {
        ...(previous[id] ?? { reps: "", weight: "", completed: false }),
        ...change,
      },
    }))
  }
  async function save() {
    if (!day?.id) return
    setError(null)
    let body: SessionInput
    try {
      const parsedEffort = actualNumber(effort, 10, true)
      if (parsedEffort !== null && parsedEffort < 1) throw Error("invalid")
      body = {
        version_id: version.id,
        day_id: day.id,
        performed_on: performedOn,
        completed,
        effort: parsedEffort,
        note: note.trim() || null,
        idempotency_key: key,
        sets: day.exercises.flatMap((exercise) =>
          exercise.sets
            .filter((set) => Boolean(set.id))
            .map((set) => {
              const value = actuals[set.id!] ?? {
                reps: "",
                weight: "",
                completed: false,
              }
              return {
                set_id: set.id!,
                completed: value.completed,
                reps: actualNumber(value.reps, 1000, true),
                weight_kg: actualNumber(value.weight, 2000),
              }
            }),
        ),
      }
    } catch {
      setError(t("activity.invalidNumber"))
      return
    }
    setSaving(true)
    try {
      await logSession(version.athlete_user_id, body)
      await cache.invalidateQueries({
        queryKey: ["workout-sessions", activeGymId, version.athlete_user_id],
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
      <div className="row" style={{ marginBlock: 16 }}>
        <Button onClick={start} disabled={!day?.id}>
          {t("activity.logWorkout")}
        </Button>
      </div>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        dismissible={!saving}
        title={t("activity.logWorkout")}
        footer={
          <>
            <Button
              variant="text"
              disabled={saving}
              onClick={() => setOpen(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void save()}>
              {t("activity.saveSession")}
            </Button>
          </>
        }
      >
        <div className="stack">
          <strong>{day?.title}</strong>
          <p>{t("activity.logHint")}</p>
          <DateField
            label={t("activity.sessionDate")}
            value={performedOn}
            onChange={(value) => setPerformedOn(value ?? todayIso())}
          />
          <label className="row">
            <input
              type="checkbox"
              checked={completed}
              onChange={(event) => setCompleted(event.target.checked)}
            />
            {t("activity.sessionDone")}
          </label>
          <TextField
            label={t("activity.effort")}
            inputMode="numeric"
            value={effort}
            onChange={(event) => setEffort(event.target.value)}
          />
          {day?.exercises.map((exercise, index) => (
            <Card key={exercise.id ?? index}>
              <h3>{exercise.exercise_name}</h3>
              {exercise.sets
                .filter((set) => Boolean(set.id))
                .map((set) => (
                  <div
                    key={set.id}
                    className="stack-sm"
                    style={{ marginBlock: 16 }}
                  >
                    <strong>
                      {t("program.set")} {formatNumber(set.set_number)}
                    </strong>
                    <label className="row">
                      <input
                        type="checkbox"
                        checked={actuals[set.id!]?.completed ?? false}
                        onChange={(event) =>
                          update(set.id!, { completed: event.target.checked })
                        }
                      />
                      {t("activity.setDone")}
                    </label>
                    <div className="m3-workout-inputs">
                      <TextField
                        label={`${t("activity.actualReps")} · ${exercise.exercise_name} · ${formatNumber(set.set_number)}`}
                        inputMode="numeric"
                        value={actuals[set.id!]?.reps ?? ""}
                        onChange={(event) =>
                          update(set.id!, { reps: event.target.value })
                        }
                      />
                      <TextField
                        label={`${t("activity.actualWeight")} · ${exercise.exercise_name} · ${formatNumber(set.set_number)}`}
                        inputMode="decimal"
                        value={actuals[set.id!]?.weight ?? ""}
                        onChange={(event) =>
                          update(set.id!, { weight: event.target.value })
                        }
                      />
                    </div>
                  </div>
                ))}
            </Card>
          ))}
          <TextField
            label={t("activity.feedback")}
            multiline
            maxLength={2000}
            value={note}
            onChange={(event) => setNote(event.target.value)}
          />
          {error ? <ErrorState message={error} /> : null}
        </div>
      </Dialog>
    </>
  )
}

export function WorkoutHistory({ athleteId }: { athleteId: string }) {
  const { activeGymId } = useAuth()
  const { t, formatNumber, formatDate } = useI18n()
  const query = useQuery({
    queryKey: ["workout-sessions", activeGymId, athleteId],
    queryFn: () => getSessions(athleteId),
    enabled: Boolean(activeGymId && athleteId),
  })
  const records = query.data ?? []
  const recent = records.filter((row) => row.performed_on >= daysAgoIso(29))
  const grouped = new Map<
    string,
    {
      name: string
      number: number
      values: { set: SessionSet; date: string; sessionId: string }[]
    }
  >()
  for (const session of records)
    for (const set of session.sets) {
      if (!set.completed || (set.reps === null && set.weight_kg === null))
        continue
      const id = `${set.exercise_id}-${set.set_number}`
      const group = grouped.get(id) ?? {
        name: set.exercise_name,
        number: set.set_number,
        values: [],
      }
      if (
        group.values.length < 2 &&
        !group.values.some((value) => value.sessionId === session.id)
      )
        group.values.push({
          set,
          date: session.performed_on,
          sessionId: session.id,
        })
      grouped.set(id, group)
    }
  const actual = (set: SessionSet | undefined) =>
    set
      ? `${set.reps === null ? "—" : formatNumber(set.reps)} × ${set.weight_kg === null ? "—" : formatNumber(set.weight_kg)} ${t("common.units.kg")}`
      : "—"
  return (
    <SectionCard
      title={t("activity.progress")}
      subtitle={t("activity.historyHint")}
    >
      {query.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : query.isError ? (
        <ErrorState
          message={translateApiError(query.error, t)}
          onRetry={() => void query.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : records.length ? (
        <div className="stack">
          <div className="m3-stat-grid">
            <Card>
              <div>{t("activity.completedSessions")}</div>
              <strong>
                {formatNumber(recent.filter((row) => row.completed).length)}
              </strong>
            </Card>
            <Card>
              <div>{t("activity.completedSets")}</div>
              <strong>
                {formatNumber(
                  recent.reduce(
                    (sum, row) =>
                      sum + row.sets.filter((set) => set.completed).length,
                    0,
                  ),
                )}
              </strong>
            </Card>
          </div>
          {grouped.size ? (
            <div className="m3-table-wrap">
              <table className="m3-table">
                <caption>{t("activity.comparison")}</caption>
                <thead>
                  <tr>
                    <th>{t("program.exercise")}</th>
                    <th>{t("activity.previous")}</th>
                    <th>{t("activity.latest")}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...grouped.entries()].map(([id, group]) => (
                    <tr key={id}>
                      <td>
                        {group.name} · {t("program.set")}{" "}
                        {formatNumber(group.number)}
                      </td>
                      <td>{actual(group.values[1]?.set)}</td>
                      <td>
                        {actual(group.values[0]?.set)}
                        <div className="muted">
                          {formatDate(group.values[0].date)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <h3>{t("activity.history")}</h3>
          {records.map((session) => (
            <details key={session.id} className="m3-card">
              <summary>
                {formatDate(session.performed_on)} · {session.day_title} ·{" "}
                {t(
                  session.completed ? "activity.complete" : "activity.partial",
                )}
              </summary>
              <p>{session.program_title}</p>
              {session.effort !== null ? (
                <p>
                  {t("activity.effort")}: {formatNumber(session.effort)}
                </p>
              ) : null}
              {session.note ? (
                <p style={{ whiteSpace: "pre-wrap" }}>{session.note}</p>
              ) : null}
              <div className="m3-table-wrap">
                <table className="m3-table">
                  <thead>
                    <tr>
                      <th>{t("program.exercise")}</th>
                      <th>{t("program.set")}</th>
                      <th>{t("activity.latest")}</th>
                      <th>{t("finance.table.status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {session.sets.map((set) => (
                      <tr key={set.set_id}>
                        <td>{set.exercise_name}</td>
                        <td>{formatNumber(set.set_number)}</td>
                        <td>{actual(set)}</td>
                        <td>
                          {t(
                            set.completed
                              ? "activity.complete"
                              : "activity.partial",
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ))}
        </div>
      ) : (
        <EmptyState title={t("activity.noHistory")} />
      )}
    </SectionCard>
  )
}
