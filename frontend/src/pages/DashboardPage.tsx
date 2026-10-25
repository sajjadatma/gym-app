import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  Activity,
  Bookmark,
  Building2,
  ClipboardList,
  Dumbbell,
  Settings,
  UserRound,
  Users,
} from "lucide-react"
import { useAuth } from "@/auth"
import {
  AthletesService,
  GymsService,
  ProgramsService,
  TemplatesService,
} from "@/client"
import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/M3"
import { useI18n } from "@/i18n"

export function DashboardPage() {
  const { t, formatNumber, formatDate } = useI18n()
  const {
    me,
    activeGym,
    activeGymId,
    activeRole,
    isSuperuser,
    isAdmin,
    isCoach,
    isAthlete,
    gyms,
  } = useAuth()
  const navigate = useNavigate()

  const adminGymQuery = useQuery({
    queryKey: ["gym", activeGymId],
    queryFn: async () =>
      (await GymsService.readGym({ path: { gym_id: activeGymId! } })).data,
    enabled: Boolean(activeGymId && isAdmin),
  })

  const athletesQuery = useQuery({
    queryKey: ["athletes", activeGymId, "dashboard", activeRole],
    queryFn: async () =>
      (
        await AthletesService.listAthletes({
          query: {
            q: "",
            is_archived: false,
            assigned_to_me: activeRole === "COACH",
            limit: 4,
          },
        })
      ).data,
    enabled: Boolean(activeGymId && (isAdmin || isCoach)),
  })

  const templatesQuery = useQuery({
    queryKey: ["templates", activeGymId, "dashboard"],
    queryFn: async () => (await TemplatesService.listTemplates()).data.data,
    enabled: Boolean(activeGymId && (isAdmin || isCoach)),
  })

  const selfQuery = useQuery({
    queryKey: ["athlete-me", activeGymId],
    queryFn: async () => (await AthletesService.readMyAthleteProfile()).data,
    enabled: Boolean(activeGymId && isAthlete),
  })

  const programsQuery = useQuery({
    queryKey: ["programs", activeGymId, me?.id, "dashboard"],
    queryFn: async () =>
      (
        await ProgramsService.listPrograms({
          path: { athlete_user_id: me!.id },
        })
      ).data.data,
    enabled: Boolean(activeGymId && isAthlete && me?.id),
  })

  if (!activeGym) {
    if (!isSuperuser) {
      return (
        <>
          <PageHeader title={t("dashboard.title")} />
          <EmptyState
            icon={<Building2 size={24} />}
            title={t("dashboard.noGym")}
            description={t("dashboard.noGymHint")}
          />
        </>
      )
    }
    return (
      <>
        <PageHeader
          title={t("dashboard.title")}
          subtitle={t("dashboard.superAdminSubtitle")}
        />
        <div className="m3-hero">
          <h2>
            {t("dashboard.welcome", { name: me?.full_name ?? me?.email ?? "" })}
          </h2>
          <div className="m3-hero__actions">
            <Button
              variant="tonal"
              icon={<Building2 size={17} />}
              onClick={() => navigate({ to: "/gyms" })}
            >
              {t("dashboard.manageGyms")}
            </Button>
          </div>
        </div>
        <div style={{ height: 20 }} />
        <div className="m3-card-grid">
          {gyms.map((gym) => (
            <Card key={gym.id}>
              <div className="row row--between">
                <strong>{gym.name}</strong>
                <Building2 size={18} className="muted" />
              </div>
              <div className="m3-entity-card__meta" style={{ marginTop: 10 }}>
                <span>
                  {t("gyms.totalCoaches")}:{" "}
                  {formatNumber(gym.stats?.coaches ?? 0)}
                </span>
                <span>
                  {t("gyms.totalAthletes")}:{" "}
                  {formatNumber(gym.stats?.athletes ?? 0)}
                </span>
                <span>
                  {t("gyms.activePrograms")}:{" "}
                  {formatNumber(gym.stats?.active_programs ?? 0)}
                </span>
              </div>
              <Button
                variant="text"
                style={{ paddingInline: 0, marginTop: 12 }}
                onClick={() =>
                  navigate({ to: "/gyms/$gymId", params: { gymId: gym.id } })
                }
              >
                {t("gyms.enter")}
              </Button>
            </Card>
          ))}
        </div>
      </>
    )
  }

  const adminStats = adminGymQuery.data?.stats ?? activeGym.stats
  const activeProgram = programsQuery.data?.find(
    (item) => item.status === "ACTIVE",
  )
  const profile = selfQuery.data?.profile
  const dashboardAthletes = athletesQuery.data?.data ?? []
  const dashboardTemplates = (templatesQuery.data ?? []).filter(
    (template) => activeRole !== "COACH" || template.created_by_id === me?.id,
  )
  const athleteCount =
    athletesQuery.data?.count ?? activeGym.stats?.athletes ?? 0
  const templateCount = dashboardTemplates.length
  const profileFields = profile
    ? [
        profile.phone,
        profile.birth_date,
        profile.height_cm,
        profile.weight_kg,
        profile.training_goal,
        profile.sports_history,
        profile.fitness_level,
        profile.limitations,
      ]
    : []
  const completedFields = profileFields.filter(Boolean).length
  const completion = profileFields.length
    ? Math.round((completedFields / profileFields.length) * 100)
    : 0

  const loading = isAdmin
    ? adminGymQuery.isLoading
    : isCoach
      ? athletesQuery.isLoading
      : selfQuery.isLoading

  if (loading) {
    return <Spinner label={t("common.loading")} />
  }

  return (
    <>
      <PageHeader
        title={t("dashboard.title")}
        subtitle={t(
          isSuperuser
            ? "dashboard.superAdminSubtitle"
            : isAthlete
              ? "dashboard.athleteSubtitle"
              : isCoach
                ? "dashboard.coachSubtitle"
                : "dashboard.adminSubtitle",
        )}
      />

      <div className="m3-hero">
        <div className="row" style={{ gap: 12 }}>
          <span
            className="m3-topbar__role"
            style={{ background: "rgba(255,255,255,.5)", color: "inherit" }}
          >
            {activeGym.name}
          </span>
          {activeRole ? (
            <span
              className="m3-topbar__role"
              style={{ background: "rgba(255,255,255,.35)", color: "inherit" }}
            >
              {t(
                activeRole === "GYM_ADMIN"
                  ? "context.adminMode"
                  : activeRole === "COACH"
                    ? "context.coachMode"
                    : "context.athleteMode",
              )}
            </span>
          ) : null}
        </div>
        <h2 style={{ marginTop: 14 }}>
          {t("dashboard.welcome", { name: me?.full_name ?? me?.email ?? "" })}
        </h2>
        <div className="m3-hero__actions">
          {activeGymId && isAdmin ? (
            <Button
              variant="tonal"
              icon={<Settings size={17} />}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/settings",
                  params: { gymId: activeGymId },
                })
              }
            >
              {t("gyms.settings")}
            </Button>
          ) : null}
          {isAdmin || isCoach ? (
            <Button
              variant="tonal"
              icon={<Users size={17} />}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/athletes",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("dashboard.manageAthletes")}
            </Button>
          ) : null}
          {isAthlete ? (
            <Button
              variant="tonal"
              icon={<ClipboardList size={17} />}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/my",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("dashboard.viewProgram")}
            </Button>
          ) : null}
        </div>
      </div>

      <div style={{ height: 20 }} />

      {isAdmin ? (
        <div className="m3-stat-grid">
          {[
            {
              label: t("dashboard.coaches"),
              value: adminStats?.coaches ?? 0,
              icon: UserRound,
            },
            {
              label: t("dashboard.athletes"),
              value: adminStats?.athletes ?? 0,
              icon: Users,
            },
            {
              label: t("dashboard.activePrograms"),
              value: adminStats?.active_programs ?? 0,
              icon: Activity,
            },
            {
              label: t("dashboard.drafts"),
              value: adminStats?.draft_programs ?? 0,
              icon: ClipboardList,
            },
            {
              label: t("dashboard.archivedPrograms"),
              value: adminStats?.archived_programs ?? 0,
              icon: Bookmark,
            },
          ].map((stat, index) => {
            const Icon = stat.icon
            return (
              <div
                key={stat.label}
                className={`m3-stat ${index === 0 ? "m3-stat--primary" : ""}`}
              >
                <div
                  className="row"
                  style={{ justifyContent: "space-between" }}
                >
                  <span className="m3-stat__label">{stat.label}</span>
                  <Icon size={17} />
                </div>
                <div className="m3-stat__value">{formatNumber(stat.value)}</div>
              </div>
            )
          })}
        </div>
      ) : null}

      {isCoach ? (
        <div className="grid-2">
          <Card>
            <div className="row row--between">
              <div>
                <div className="m3-stat__label">
                  {t("dashboard.myAthletes")}
                </div>
                <div className="m3-stat__value">
                  {formatNumber(athleteCount)}
                </div>
              </div>
              <Users size={24} className="muted" />
            </div>
            <Button
              variant="text"
              style={{ paddingInline: 0, marginTop: 12 }}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/athletes",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("dashboard.manageAthletes")}
            </Button>
          </Card>
          <Card>
            <div className="row row--between">
              <div>
                <div className="m3-stat__label">
                  {t("dashboard.myTemplates")}
                </div>
                <div className="m3-stat__value">
                  {formatNumber(templateCount)}
                </div>
              </div>
              <Bookmark size={24} className="muted" />
            </div>
            <Button
              variant="text"
              style={{ paddingInline: 0, marginTop: 12 }}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/templates",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("dashboard.manageTemplates")}
            </Button>
          </Card>
        </div>
      ) : null}

      {isAthlete ? (
        <div className="grid-2">
          <Card>
            <div className="row row--between">
              <div>
                <div className="m3-stat__label">
                  {t("dashboard.activeProgram")}
                </div>
                {activeProgram ? (
                  <>
                    <div
                      className="m3-athlete-hero__program"
                      style={{ marginTop: 6 }}
                    >
                      {activeProgram.title}
                    </div>
                    <div className="m3-athlete-hero__meta">
                      <span>
                        {t("program.versionLabel", {
                          version: formatNumber(activeProgram.version_number),
                        })}
                      </span>
                      <span>{activeProgram.coach_name ?? ""}</span>
                      {activeProgram.start_date ? (
                        <span>{formatDate(activeProgram.start_date)}</span>
                      ) : null}
                    </div>
                  </>
                ) : (
                  <p className="muted" style={{ marginTop: 6 }}>
                    {t("dashboard.noActiveProgram")}
                  </p>
                )}
              </div>
              <ClipboardList size={26} className="muted" />
            </div>
            {activeProgram ? (
              <Button
                variant="tonal"
                style={{ marginTop: 16 }}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/my/programs/$versionId",
                    params: {
                      gymId: activeGymId!,
                      versionId: activeProgram.id,
                    },
                  })
                }
              >
                {t("dashboard.viewProgram")}
              </Button>
            ) : null}
          </Card>
          <Card>
            <div className="row row--between">
              <div>
                <div className="m3-stat__label">
                  {t("dashboard.profileCompletion")}
                </div>
                <div className="m3-stat__value">
                  {formatNumber(completion)}%
                </div>
                <p className="m3-stat__hint">
                  {t("dashboard.profileCompletionHint")}
                </p>
              </div>
              <UserRound size={26} className="muted" />
            </div>
            <Button
              variant="text"
              style={{ paddingInline: 0, marginTop: 12 }}
              onClick={() =>
                navigate({
                  to: "/gyms/$gymId/my/profile",
                  params: { gymId: activeGymId! },
                })
              }
            >
              {t("dashboard.completeProfile")}
            </Button>
          </Card>
        </div>
      ) : null}

      {isAdmin ? (
        <div className="grid-2" style={{ marginTop: 20 }}>
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">
                  {t("dashboard.quickActions")}
                </h2>
                <p className="m3-section__subtitle">
                  {t("dashboard.adminSubtitle")}
                </p>
              </div>
            </div>
            <div className="row">
              <Button
                variant="tonal"
                icon={<Users size={17} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/athletes",
                    params: { gymId: activeGymId! },
                  })
                }
              >
                {t("nav.athletes")}
              </Button>
              <Button
                variant="outlined"
                icon={<UserRound size={17} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/members",
                    params: { gymId: activeGymId! },
                  })
                }
              >
                {t("nav.members")}
              </Button>
              <Button
                variant="outlined"
                icon={<Bookmark size={17} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/templates",
                    params: { gymId: activeGymId! },
                  })
                }
              >
                {t("nav.templates")}
              </Button>
              <Button
                variant="outlined"
                icon={<Dumbbell size={17} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/exercises",
                    params: { gymId: activeGymId! },
                  })
                }
              >
                {t("nav.exercises")}
              </Button>
            </div>
          </Card>
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("athletes.title")}</h2>
                <p className="m3-section__subtitle">{t("athletes.subtitle")}</p>
              </div>
              <Button
                variant="text"
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/athletes",
                    params: { gymId: activeGymId! },
                  })
                }
              >
                {t("common.more")}
              </Button>
            </div>
            {dashboardAthletes.length ? (
              <div className="stack-sm">
                {dashboardAthletes.slice(0, 4).map((athlete) => (
                  <button
                    key={athlete.user_id}
                    type="button"
                    className="m3-version-row"
                    style={{ width: "100%", border: 0, textAlign: "start" }}
                    onClick={() =>
                      navigate({
                        to: "/gyms/$gymId/athletes/$athleteId",
                        params: {
                          gymId: activeGymId!,
                          athleteId: athlete.user_id,
                        },
                      })
                    }
                  >
                    <div className="m3-version-row__main">
                      <UserRound size={18} className="muted" />
                      <div>
                        <div className="m3-version-row__title">
                          {athlete.full_name ?? athlete.email}
                        </div>
                        <div className="m3-version-row__meta">
                          {athlete.coach_name ?? t("athletes.noCoach")}
                        </div>
                      </div>
                    </div>
                    {athlete.active_program_title ? (
                      <StatusBadge status="active" />
                    ) : (
                      <span className="m3-status m3-status--archived">
                        {t("athletes.noActiveProgram")}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                title={t("athletes.empty")}
                description={t("athletes.emptyHint")}
              />
            )}
          </Card>
        </div>
      ) : null}
    </>
  )
}
