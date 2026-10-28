import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { ArrowLeft, ArrowRight, Printer } from "lucide-react"
import { type CSSProperties, useEffect } from "react"
import { apiAssetUrl, translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { ProgramsService } from "@/client"
import { Button, ErrorState, Spinner } from "@/components/M3"
import { useI18n } from "@/i18n"
import { workoutDayLabel } from "@/lib/workoutDayLabel"

export function PrintPage({
  versionId,
  gymId,
}: {
  versionId: string
  gymId?: string
}) {
  const { t, direction, formatDate, formatNumber } = useI18n()
  const { activeGym, activeGymId, activeRole, setActiveGym } = useAuth()
  const navigate = useNavigate()
  const contextGymId = gymId ?? activeGymId ?? null
  const contextReady = Boolean(contextGymId) && activeGymId === contextGymId

  useEffect(() => {
    if (gymId && activeGymId !== gymId) setActiveGym(gymId)
  }, [activeGymId, gymId, setActiveGym])

  const versionQuery = useQuery({
    queryKey: ["print-version", activeGymId, versionId],
    queryFn: async () =>
      (
        await ProgramsService.readProgramVersion({
          path: { version_id: versionId },
        })
      ).data,
    enabled: contextReady,
  })

  useEffect(() => {
    if (!versionQuery.data) return
    const previous = document.title
    document.title = `${versionQuery.data.title} · ${t("print.title")}`
    return () => {
      document.title = previous
    }
  }, [versionQuery.data, t])

  if (!contextGymId) {
    return (
      <div className="m3-print-page">
        <ErrorState message={t("print.missingContext")} />
      </div>
    )
  }

  if (!contextReady) {
    return (
      <div
        style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}
      >
        <Spinner label={t("common.loading")} />
      </div>
    )
  }

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
  const brandPrimary = activeGym?.brand_primary_color ?? "#006c51"
  const brandAccent = activeGym?.brand_accent_color ?? brandPrimary
  const sheetStyle = {
    "--print-brand": brandPrimary,
    "--print-accent": brandAccent,
  } as CSSProperties
  const BackIcon = direction === "rtl" ? ArrowRight : ArrowLeft
  const back = () => {
    if (activeRole === "ATHLETE") {
      navigate({
        to: "/gyms/$gymId/my/programs/$versionId",
        params: { gymId: activeGymId!, versionId },
      })
      return
    }
    navigate({
      to: "/gyms/$gymId/programs/$versionId/edit",
      params: { gymId: activeGymId!, versionId },
    })
  }

  return (
    <div className="m3-print-page">
      <div className="m3-print-toolbar">
        <Button variant="text" icon={<BackIcon size={16} />} onClick={back}>
          {t("print.back")}
        </Button>
        <span className="m3-print-toolbar__hint">{t("print.hint")}</span>
        <Button icon={<Printer size={16} />} onClick={() => window.print()}>
          {t("print.printButton")}
        </Button>
      </div>

      <div className="m3-print-sheet" dir={direction} style={sheetStyle}>
        <header className="m3-print-header">
          <div>
            <div className="m3-print-club">
              {activeGym?.logo_url ? (
                <img
                  className="m3-print-club__logo"
                  src={apiAssetUrl(activeGym.logo_url)}
                  alt=""
                  onError={(event) => {
                    event.currentTarget.style.display = "none"
                  }}
                />
              ) : null}
              <div>
                <div className="m3-print-header__brand">
                  {activeGym?.name ?? t("app.name")}
                </div>
                <div className="m3-print-header__app">ASCORA</div>
              </div>
            </div>
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

        <footer className="m3-print-footer">ASCORA · {t("app.tagline")}</footer>
      </div>
    </div>
  )
}
