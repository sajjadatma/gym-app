import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ArrowRight, Printer } from "lucide-react"
import { useEffect } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { ProgramsService } from "@/client"
import { Button, ErrorState, Spinner } from "@/components/M3"
import { useI18n } from "@/i18n"
import { workoutDayLabel } from "@/lib/workoutDayLabel"

export function PrintPage({ versionId }: { versionId: string }) {
  const { t, direction, formatDate, formatNumber } = useI18n()
  const { activeGym, activeGymId, activeRole } = useAuth()
  const navigate = useNavigate()

  const versionQuery = useQuery({
    queryKey: ["print-version", activeGymId, versionId],
    queryFn: async () =>
      (
        await ProgramsService.readProgramVersion({
          path: { version_id: versionId },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })

  useEffect(() => {
    if (!versionQuery.data) return
    const previous = document.title
    document.title = `${versionQuery.data.title} · ${t("print.title")}`
    return () => {
      document.title = previous
    }
  }, [versionQuery.data, t])

  if (versionQuery.isLoading) {
    return (
      <div
        style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}
      >
        <Spinner label={t("common.loading")} />
      </div>
    )
  }
  if (versionQuery.isError || !versionQuery.data) {
    return (
      <div style={{ padding: 24 }}>
        <ErrorState
          message={translateApiError(versionQuery.error, t)}
          onRetry={() => versionQuery.refetch()}
          retryLabel={t("common.retry")}
        />
      </div>
    )
  }

  const version = versionQuery.data
  const back = () => {
    if (activeRole === "ATHLETE") {
      navigate({
        to: "/my/programs/$versionId",
        params: { versionId },
      })
      return
    }
    navigate({
      to: "/programs/$versionId/edit",
      params: { versionId },
    })
  }

  return (
    <div className="m3-print-page">
      <div className="m3-print-toolbar">
        <Button variant="text" icon={<ArrowRight size={16} />} onClick={back}>
          {t("print.back")}
        </Button>
        <span className="m3-print-toolbar__hint">{t("print.hint")}</span>
        <Button icon={<Printer size={16} />} onClick={() => window.print()}>
          {t("print.printButton")}
        </Button>
      </div>

      <div className="m3-print-sheet" dir={direction}>
        <header className="m3-print-header">
          <div>
            <div className="m3-print-header__brand">{t("app.name")}</div>
            <h1>{version.title}</h1>
            <div style={{ fontSize: 11, marginTop: 4 }}>
              {t("print.preparedFor")}:{" "}
              <strong>{version.athlete_name ?? ""}</strong>
            </div>
          </div>
          <div style={{ textAlign: "end", fontSize: 10.5 }}>
            <div>
              {t("print.gym")}: <strong>{activeGym?.name ?? ""}</strong>
            </div>
            <div>
              {t("print.preparedBy")}:{" "}
              <strong>{version.coach_name ?? ""}</strong>
            </div>
            <div>
              {t("print.version")}:{" "}
              <strong>{formatNumber(version.version_number)}</strong>
            </div>
            <div>
              {t("print.date")}:{" "}
              <strong>{formatDate(new Date().toISOString())}</strong>
            </div>
          </div>
        </header>

        <div className="m3-print-meta">
          {version.goal ? (
            <div>
              <strong>{t("program.goal")}:</strong> {version.goal}
            </div>
          ) : null}
          {version.start_date ? (
            <div>
              <strong>{t("program.startDate")}:</strong>{" "}
              {formatDate(version.start_date)}
            </div>
          ) : null}
          {version.end_date ? (
            <div>
              <strong>{t("program.endDate")}:</strong>{" "}
              {formatDate(version.end_date)}
            </div>
          ) : null}
        </div>

        {version.notes ? (
          <p style={{ fontSize: 10.5, marginBottom: 14, color: "#404943" }}>
            {version.notes}
          </p>
        ) : null}

        {version.days.map((day, dayIndex) => (
          <section className="m3-print-day" key={day.id ?? dayIndex}>
            <h2 className="m3-print-day__title">
              {workoutDayLabel(
                day,
                t("program.day"),
                formatNumber(dayIndex + 1),
              )}
            </h2>
            {day.notes ? (
              <p
                style={{ fontSize: 10, color: "#404943", padding: "4px 10px" }}
              >
                {day.notes}
              </p>
            ) : null}
            {day.exercises.map((exercise, exerciseIndex) => (
              <div
                className="m3-print-exercise"
                key={exercise.id ?? `${exercise.exercise_id}-${exerciseIndex}`}
              >
                <div className="m3-print-exercise__head">
                  <span className="m3-print-exercise__name">
                    {formatNumber(exerciseIndex + 1)}. {exercise.exercise_name}
                  </span>
                  <span style={{ color: "#707973" }}>
                    {exercise.muscle_group}
                  </span>
                </div>
                {exercise.notes ? (
                  <p className="m3-print-exercise__notes">{exercise.notes}</p>
                ) : null}
                <table className="m3-print-sets">
                  <thead>
                    <tr>
                      <th>{t("print.set")}</th>
                      <th>{t("print.reps")}</th>
                      <th>{t("print.weight")}</th>
                      <th>{t("print.rest")}</th>
                      <th>{t("program.duration")}</th>
                      <th>{t("print.notes")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exercise.sets.map((set, setIndex) => (
                      <tr key={set.id ?? setIndex}>
                        <td>{formatNumber(setIndex + 1)}</td>
                        <td>
                          {set.reps_min === set.reps_max || set.reps_max == null
                            ? formatNumber(set.reps_min ?? 0)
                            : `${formatNumber(set.reps_min ?? 0)}–${formatNumber(set.reps_max)}`}
                        </td>
                        <td>
                          {set.weight_kg != null
                            ? `${formatNumber(set.weight_kg)} ${t("common.units.kg")}`
                            : (set.intensity ?? "—")}
                        </td>
                        <td>
                          {set.rest_seconds != null
                            ? `${formatNumber(set.rest_seconds)} ${t("common.units.seconds")}`
                            : "—"}
                        </td>
                        <td>
                          {set.duration_seconds != null
                            ? `${formatNumber(set.duration_seconds)} ${t("common.units.seconds")}`
                            : "—"}
                        </td>
                        <td>{set.note ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </section>
        ))}

        <footer className="m3-print-footer">
          {t("app.name")} · {t("app.tagline")}
        </footer>
      </div>
    </div>
  )
}
