import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { CalendarDays, ClipboardList, Printer, UserRound } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { ProgramsService } from "@/client"
import {
  Button,
  Card,
  ErrorState,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { workoutDayLabel } from "@/lib/workoutDayLabel"

export function MyProgramDetailPage({ versionId }: { versionId: string }) {
  const { t, formatDate, formatNumber } = useI18n()
  const { activeGym, activeGymId } = useAuth()
  const navigate = useNavigate()
  const [selectedDay, setSelectedDay] = useState(0)

  const versionQuery = useQuery({
    queryKey: ["program-version", activeGymId, versionId],
    queryFn: async () =>
      (
        await ProgramsService.readProgramVersion({
          path: { version_id: versionId },
        })
      ).data,
    enabled: Boolean(activeGymId),
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("program.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }
  if (versionQuery.isLoading) return <Spinner label={t("common.loading")} />
  if (versionQuery.isError || !versionQuery.data) {
    return (
      <ErrorState
        message={translateApiError(versionQuery.error, t)}
        onRetry={() => versionQuery.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  const version = versionQuery.data
  const day = version.days[selectedDay] ?? version.days[0]

  function formatRest(seconds: number | null | undefined) {
    if (!seconds) return "—"
    return `${formatNumber(seconds)} ${t("common.units.seconds")}`
  }

  return (
    <>
      <PageHeader
        title={version.title}
        subtitle={`${version.coach_name ?? ""} · ${t("program.versionLabel", {
          version: formatNumber(version.version_number),
        })}`}
        onBack={() =>
          navigate({
            to: "/gyms/$gymId/my",
            params: { gymId: activeGymId! },
          })
        }
        backLabel={t("common.back")}
        actions={
          <>
            <StatusBadge status={version.status.toLowerCase()} />
            <Button
              variant="outlined"
              icon={<Printer size={16} />}
              onClick={() => window.open(`/print/${version.id}`, "_blank")}
            >
              {t("common.print")}
            </Button>
          </>
        }
      />

      <div className="m3-athlete-hero">
        <div>
          <div className="m3-athlete-hero__program">{version.title}</div>
          <div className="m3-athlete-hero__meta">
            <span>
              <CalendarDays size={13} style={{ verticalAlign: "middle" }} />{" "}
              {t("program.days")}: {formatNumber(version.days.length)}
            </span>
            {version.coach_name ? (
              <span>
                <UserRound size={13} style={{ verticalAlign: "middle" }} />{" "}
                {version.coach_name}
              </span>
            ) : null}
            {version.start_date ? (
              <span>{formatDate(version.start_date)}</span>
            ) : null}
          </div>
          {version.goal ? (
            <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
              {version.goal}
            </p>
          ) : null}
        </div>
        <ClipboardList size={28} className="muted" />
      </div>

      {version.days.length ? (
        <>
          <div
            className="m3-day-picker"
            role="tablist"
            aria-label={t("program.days")}
          >
            {version.days.map((item, index) => (
              <button
                key={item.id ?? index}
                type="button"
                role="tab"
                aria-selected={selectedDay === index}
                className={`m3-day-pill ${selectedDay === index ? "is-active" : ""}`}
                onClick={() => setSelectedDay(index)}
              >
                {workoutDayLabel(
                  item,
                  t("program.day"),
                  formatNumber(index + 1),
                )}
              </button>
            ))}
          </div>

          {day ? (
            <div className="stack">
              {day.notes ? (
                <div className="m3-inline-alert m3-inline-alert--info">
                  {day.notes}
                </div>
              ) : null}
              {day.exercises.map((exercise, index) => (
                <div
                  key={exercise.id ?? `${exercise.exercise_id}-${index}`}
                  className="m3-athlete-exercise"
                >
                  <div className="m3-athlete-exercise__head">
                    <div>
                      <div className="m3-athlete-exercise__name">
                        {formatNumber(index + 1)}. {exercise.exercise_name}
                      </div>
                      <div className="m3-athlete-exercise__group">
                        {exercise.muscle_group}
                      </div>
                    </div>
                  </div>
                  {exercise.notes ? (
                    <div className="m3-athlete-exercise__notes">
                      {exercise.notes}
                    </div>
                  ) : null}
                  <div className="m3-sets-list">
                    {exercise.sets.map((set, setIndex) => (
                      <div className="m3-set-row" key={set.id ?? setIndex}>
                        <span className="m3-set-row__number">
                          {formatNumber(setIndex + 1)}
                        </span>
                        <div>
                          <span className="m3-set-row__label">
                            {t("print.reps")}
                          </span>
                          <span className="m3-set-row__value">
                            {set.reps_min === set.reps_max ||
                            set.reps_max == null
                              ? formatNumber(set.reps_min ?? 0)
                              : `${formatNumber(set.reps_min ?? 0)}–${formatNumber(set.reps_max)}`}
                          </span>
                        </div>
                        <div>
                          <span className="m3-set-row__label">
                            {t("print.weight")}
                          </span>
                          <span className="m3-set-row__value">
                            {set.weight_kg != null
                              ? `${formatNumber(set.weight_kg)} ${t("common.units.kg")}`
                              : (set.intensity ?? "—")}
                          </span>
                        </div>
                        <div>
                          <span className="m3-set-row__label">
                            {t("print.rest")}
                          </span>
                          <span className="m3-set-row__value">
                            {formatRest(set.rest_seconds)}
                          </span>
                        </div>
                        <div>
                          <span className="m3-set-row__label">
                            {t("program.duration")}
                          </span>
                          <span className="m3-set-row__value">
                            {set.duration_seconds
                              ? `${formatNumber(set.duration_seconds)} ${t("common.units.seconds")}`
                              : "—"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {exercise.sets.some((set) => set.note) ? (
                    <div className="stack-sm" style={{ marginTop: 8 }}>
                      {exercise.sets
                        .filter((set) => set.note)
                        .map((set, setIndex) => (
                          <p
                            key={set.id ?? setIndex}
                            className="muted"
                            style={{ fontSize: 11.5 }}
                          >
                            {t("program.set")} {formatNumber(set.set_number)}:{" "}
                            {set.note}
                          </p>
                        ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <Card>
          <p className="muted">{t("program.noDays")}</p>
        </Card>
      )}
    </>
  )
}
