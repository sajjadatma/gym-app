import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { CalendarDays, ClipboardList, Printer, UserRound } from "lucide-react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { AthletesService, ProgramsService } from "@/client"
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/M3"
import { useI18n } from "@/i18n"

export function MyProgramPage() {
  const { t, formatDate, formatNumber } = useI18n()
  const { activeGym, activeGymId, me, activeRole } = useAuth()
  const navigate = useNavigate()

  const profileQuery = useQuery({
    queryKey: ["athlete-me", activeGymId],
    queryFn: async () => (await AthletesService.readMyAthleteProfile()).data,
    enabled: Boolean(activeGymId && activeRole === "ATHLETE"),
  })

  const programsQuery = useQuery({
    queryKey: ["programs", activeGymId, me?.id, "my"],
    queryFn: async () =>
      (
        await ProgramsService.listPrograms({
          path: { athlete_user_id: me!.id },
        })
      ).data.data,
    enabled: Boolean(activeGymId && me?.id && activeRole === "ATHLETE"),
  })

  if (!activeGym) {
    return (
      <PageHeader title={t("my.title")} subtitle={t("context.noGymHint")} />
    )
  }

  if (activeRole !== "ATHLETE") {
    return (
      <>
        <PageHeader title={t("my.title")} subtitle={t("my.subtitle")} />
        <ErrorState message={t("errors.athlete_staff_access_required")} />
      </>
    )
  }

  if (profileQuery.isLoading || programsQuery.isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (profileQuery.isError || programsQuery.isError) {
    return (
      <ErrorState
        message={translateApiError(
          profileQuery.error ?? programsQuery.error,
          t,
        )}
        onRetry={() => {
          void profileQuery.refetch()
          void programsQuery.refetch()
        }}
        retryLabel={t("common.retry")}
      />
    )
  }

  const profile = profileQuery.data?.profile
  const programs = programsQuery.data ?? []
  const active = programs.find((program) => program.status === "ACTIVE")
  const history = programs.filter((program) => program.status !== "ACTIVE")

  return (
    <>
      <PageHeader
        title={t("my.title")}
        subtitle={`${activeGym.name} · ${t("my.subtitle")}`}
        actions={
          <Button
            variant="outlined"
            icon={<UserRound size={16} />}
            onClick={() =>
              navigate({
                to: "/gyms/$gymId/my/profile",
                params: { gymId: activeGymId! },
              })
            }
          >
            {t("nav.myProfile")}
          </Button>
        }
      />

      {active ? (
        <div className="m3-athlete-hero">
          <div>
            <span className="m3-status m3-status--active">
              {t("my.activeProgram")}
            </span>
            <div className="m3-athlete-hero__program" style={{ marginTop: 8 }}>
              {active.title}
            </div>
            <div className="m3-athlete-hero__meta">
              <span>
                <CalendarDays size={13} style={{ verticalAlign: "middle" }} />{" "}
                {t("program.days")}: {formatNumber(active.day_count)}
              </span>
              <span>{active.coach_name ?? ""}</span>
              {active.start_date ? (
                <span>{formatDate(active.start_date)}</span>
              ) : null}
            </div>
            {active.goal ? (
              <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
                {active.goal}
              </p>
            ) : null}
          </div>
          <div className="row" style={{ gap: 8 }}>
            <Button
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/my/programs/$versionId",
                  params: { gymId: activeGymId!, versionId: active.id },
                })
              }
            >
              {t("my.view")}
            </Button>
            <Button
              variant="outlined"
              icon={<Printer size={16} />}
              onClick={() => window.open(`/print/${active.id}`, "_blank")}
            >
              {t("common.print")}
            </Button>
          </div>
        </div>
      ) : (
        <EmptyState
          icon={<ClipboardList size={26} />}
          title={t("my.noActiveProgram")}
          description={t("my.noActiveProgramHint")}
        />
      )}

      <div style={{ height: 20 }} />

      <div className="grid-2">
        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("my.history")}</h2>
              <p className="m3-section__subtitle">{t("my.subtitle")}</p>
            </div>
          </div>
          {history.length ? (
            <div className="stack-sm">
              {history.map((program) => (
                <button
                  key={program.id}
                  type="button"
                  className="m3-version-row"
                  style={{ border: 0, width: "100%", textAlign: "start" }}
                  onClick={() =>
                    navigate({
                      to: "/gyms/$gymId/my/programs/$versionId",
                      params: { gymId: activeGymId!, versionId: program.id },
                    })
                  }
                >
                  <div className="m3-version-row__main">
                    <ClipboardList size={18} className="muted" />
                    <div>
                      <div className="m3-version-row__title">
                        {program.title}
                      </div>
                      <div className="m3-version-row__meta">
                        {t("program.versionLabel", {
                          version: formatNumber(program.version_number),
                        })}{" "}
                        · {formatDate(program.created_at)}
                      </div>
                    </div>
                  </div>
                  <StatusBadge status={program.status.toLowerCase()} />
                </button>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ fontSize: 12 }}>
              {t("my.noHistory")}
            </p>
          )}
        </Card>

        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("my.profileTitle")}</h2>
              <p className="m3-section__subtitle">{t("my.profileSubtitle")}</p>
            </div>
            <UserRound size={22} className="muted" />
          </div>
          <div className="stack-sm">
            {profile?.training_goal ? (
              <div>
                <div className="m3-stat__label">{t("my.goal")}</div>
                <div>{profile.training_goal}</div>
              </div>
            ) : null}
            {profile?.height_cm || profile?.weight_kg ? (
              <div className="row" style={{ gap: 20 }}>
                {profile?.height_cm ? (
                  <div>
                    <div className="m3-stat__label">{t("athletes.height")}</div>
                    <div>
                      {formatNumber(profile.height_cm)} {t("common.units.cm")}
                    </div>
                  </div>
                ) : null}
                {profile?.weight_kg ? (
                  <div>
                    <div className="m3-stat__label">{t("athletes.weight")}</div>
                    <div>
                      {formatNumber(profile.weight_kg)} {t("common.units.kg")}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
            <Button
              variant="text"
              style={{ paddingInline: 0 }}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/my/profile",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("my.updateProfile")}
            </Button>
          </div>
        </Card>
      </div>
    </>
  )
}
