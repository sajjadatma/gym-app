import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { translateApiError } from "@/api"
import {
  Card,
  EmptyState,
  ErrorState,
  SectionCard,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { getGymTasks } from "@/lib/activity-api"

export function GymTasks({ gymId }: { gymId: string }) {
  const { t, formatNumber } = useI18n()
  const query = useQuery({
    queryKey: ["gym-tasks", gymId],
    queryFn: () => getGymTasks(gymId),
  })
  return (
    <SectionCard
      title={t("activity.today")}
      actions={
        <Link to="/gyms/$gymId/coach-plan" params={{ gymId }}>
          {t("activity.allRequests")}
        </Link>
      }
    >
      {query.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : query.isError ? (
        <ErrorState
          message={translateApiError(query.error, t)}
          onRetry={() => void query.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : query.data ? (
        <div className="stack">
          <div className="m3-stat-grid">
            {[
              [t("activity.requested"), query.data.requested_count],
              [t("activity.preparing"), query.data.in_progress_count],
              [t("activity.noProgram"), query.data.without_program_count],
            ].map(([label, count]) => (
              <Card key={String(label)}>
                <div className="m3-stat__label">{label}</div>
                <strong className="m3-stat__value">
                  {formatNumber(Number(count))}
                </strong>
              </Card>
            ))}
          </div>
          {query.data.requests.length ? (
            query.data.requests.map((request) => (
              <div key={request.id} className="m3-version-row">
                <div>
                  <strong>{request.athlete_name}</strong>
                  <div className="muted">
                    {request.plan_title} ·{" "}
                    {t(
                      request.status === "IN_PROGRESS"
                        ? "activity.preparing"
                        : "activity.requested",
                    )}
                  </div>
                </div>
                {request.program_version_id ? (
                  <Link
                    to="/gyms/$gymId/programs/$versionId/edit"
                    params={{ gymId, versionId: request.program_version_id }}
                  >
                    {t("activity.continue")}
                  </Link>
                ) : (
                  <Link
                    to="/gyms/$gymId/athletes/$athleteId"
                    params={{ gymId, athleteId: request.athlete_user_id }}
                  >
                    {t("activity.start")}
                  </Link>
                )}
              </div>
            ))
          ) : (
            <EmptyState title={t("activity.noTasks")} />
          )}
          {query.data.without_program.map((athlete) => (
            <div key={athlete.id} className="row row--between">
              <span>
                {athlete.name} · {t("activity.noProgram")}
              </span>
              <Link
                to="/gyms/$gymId/athletes/$athleteId"
                params={{ gymId, athleteId: athlete.id }}
              >
                {t("activity.start")}
              </Link>
            </div>
          ))}
        </div>
      ) : null}
    </SectionCard>
  )
}
