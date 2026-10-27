import { useQuery } from "@tanstack/react-query"
import { useNavigate, useRouter } from "@tanstack/react-router"
import {
  CalendarDays,
  ClipboardList,
  Download,
  ExternalLink,
  FileUp,
  History,
  Mail,
  Phone,
  ShieldAlert,
  UserRound,
  Users,
} from "lucide-react"
import type { ReactNode } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  PeopleService,
  type PersonAssignmentPublic,
  type PersonBodyFilePublic,
  type PersonHistoryEvent,
  type PersonProgramPublic,
} from "@/client"
import { client } from "@/client/client.gen"
import {
  Avatar,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/M3"
import { type TranslationKey, useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

type Kind = "ATHLETE" | "COACH"

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function DetailField({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  const empty =
    children === null ||
    children === undefined ||
    (typeof children === "string" && children.trim() === "")
  return (
    <div className="person-field">
      <span className="person-field__label">{label}</span>
      <span className="person-field__value">{empty ? "—" : children}</span>
    </div>
  )
}

export function PersonOverviewPage({
  userId,
  gymId,
  kind,
}: {
  userId: string
  gymId: string
  kind: Kind
}) {
  const { t, formatDate, formatDateTime, formatNumber } = useI18n()
  const { setActiveGym } = useAuth()
  const navigate = useNavigate()
  const router = useRouter()
  const { show } = useSnackbar()

  const overviewQuery = useQuery({
    queryKey: ["person-overview", gymId, userId, kind],
    queryFn: async () =>
      (
        await PeopleService.readPersonOverview({
          path: { user_id: userId },
          query: { gym_id: gymId, kind },
        })
      ).data,
    enabled: Boolean(gymId && userId),
    staleTime: 0,
    refetchOnWindowFocus: true,
  })

  function roleLabel(role: string) {
    if (role === "GYM_ADMIN") return t("members.admin")
    if (role === "COACH") return t("members.coach")
    return t("context.athlete")
  }

  async function downloadFile(file: PersonBodyFilePublic) {
    try {
      const response = await client.instance.get(
        `/api/v1/people/${userId}/body-files/${file.id}`,
        { params: { gym_id: file.gym_id }, responseType: "blob" },
      )
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = file.original_name
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      show(translateApiError(err, t), "error")
    }
  }

  function eventDescription(event: PersonHistoryEvent) {
    const data = event.data ?? {}
    switch (event.event) {
      case "account.created":
        return String(data.email ?? "")
      case "membership.joined": {
        const roles = Array.isArray(data.roles)
          ? data.roles.map((role) => roleLabel(String(role))).join(" · ")
          : ""
        return roles
      }
      case "athlete.profile_created":
        return data.archived ? t("status.archived") : t("status.active")
      case "assignment.started":
      case "assignment.ended":
        return `${t("person.programs.athlete")}: ${
          data.athlete ?? "—"
        } · ${t("person.programs.coach")}: ${data.coach ?? "—"}`
      case "program.version_created":
      case "program.version_published":
      case "program.version_archived":
        return `${data.title ?? "—"} · ${t("program.versionLabel", {
          version: formatNumber(Number(data.version ?? 0)),
        })} · ${t("person.programs.athlete")}: ${data.athlete ?? "—"}`
      case "athlete.body_file_uploaded":
        return `${data.file ?? "—"} · ${formatBytes(Number(data.size ?? 0))}`
      default:
        return ""
    }
  }

  function assignmentRow(assignment: PersonAssignmentPublic) {
    return (
      <div key={assignment.id} className="person-list__item">
        <UserRound size={17} className="muted" aria-hidden />
        <div className="person-list__main">
          <strong>
            {kind === "COACH"
              ? (assignment.athlete_name ?? "—")
              : (assignment.coach_name ?? "—")}
          </strong>
          <span className="muted">
            {assignment.gym_name} · {formatDate(assignment.started_at)} —{" "}
            {assignment.ended_at
              ? formatDate(assignment.ended_at)
              : t("status.active")}
          </span>
        </div>
        {assignment.assigned_by_name ? (
          <span className="muted person-list__side">
            {t("person.assignment.by", {
              name: assignment.assigned_by_name,
            })}
          </span>
        ) : null}
      </div>
    )
  }

  function programsSection({
    programs,
    title,
    hint,
    emptyTitle,
    emptyHint,
    id,
  }: {
    programs: PersonProgramPublic[]
    title: string
    hint: string
    emptyTitle: string
    emptyHint: string
    id?: string
  }) {
    if (!programs.length) {
      return (
        <Card id={id}>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{title}</h2>
              <p className="m3-section__subtitle">{hint}</p>
            </div>
          </div>
          <EmptyState
            icon={<ClipboardList size={26} />}
            title={emptyTitle}
            description={emptyHint}
          />
        </Card>
      )
    }
    return (
      <Card id={id}>
        <div className="m3-section__header">
          <div>
            <h2 className="m3-section__title">{title}</h2>
            <p className="m3-section__subtitle">{hint}</p>
          </div>
          <ClipboardList size={22} className="muted" aria-hidden />
        </div>
        <div className="person-programs">
          {programs.map((program) => (
            <details key={program.id} className="person-program">
              <summary className="person-program__summary">
                <div className="person-program__title">
                  <ClipboardList size={18} className="muted" aria-hidden />
                  <div>
                    <strong>{program.title}</strong>
                    <span className="muted">
                      {t("program.versionLabel", {
                        version: formatNumber(program.version_number),
                      })}
                      {program.gym_name ? ` · ${program.gym_name}` : ""}
                    </span>
                  </div>
                </div>
                <div className="person-program__meta">
                  <StatusBadge status={program.status.toLowerCase()} />
                  <span>
                    {t("program.days")}: {formatNumber(program.day_count)}
                  </span>
                  {program.start_date ? (
                    <span>
                      <CalendarDays size={13} aria-hidden />{" "}
                      {formatDate(program.start_date)}
                      {program.end_date
                        ? ` — ${formatDate(program.end_date)}`
                        : ""}
                    </span>
                  ) : null}
                </div>
              </summary>
              <div className="person-program__body">
                <div className="person-program__actions">
                  <div className="row" style={{ gap: 14 }}>
                    {program.goal ? (
                      <span>
                        {t("person.programs.goal")}: {program.goal}
                      </span>
                    ) : null}
                    <span>
                      {t("person.programs.coach")}: {program.coach_name ?? "—"}
                    </span>
                    {program.athlete_name ? (
                      <span>
                        {t("person.programs.athlete")}: {program.athlete_name}
                      </span>
                    ) : null}
                    <span>
                      {t("person.programs.revision")}:{" "}
                      {formatNumber(program.revision)}
                    </span>
                    <span>
                      {t("person.programs.created")}:{" "}
                      {formatDate(program.created_at)}
                    </span>
                    {program.published_at ? (
                      <span>
                        {t("person.programs.published")}:{" "}
                        {formatDate(program.published_at)}
                      </span>
                    ) : null}
                    {program.archived_at ? (
                      <span>
                        {t("person.programs.archived")}:{" "}
                        {formatDate(program.archived_at)}
                      </span>
                    ) : null}
                  </div>
                  <Button
                    variant="outlined"
                    size="sm"
                    icon={<ExternalLink size={14} />}
                    onClick={() => {
                      setActiveGym(program.gym_id)
                      navigate({
                        to: "/gyms/$gymId/programs/$versionId/edit",
                        params: {
                          gymId: program.gym_id,
                          versionId: program.id,
                        },
                      })
                    }}
                  >
                    {t("common.open")}
                  </Button>
                </div>
                {program.notes ? (
                  <p className="person-program__notes">
                    <strong>{t("person.programs.notes")}:</strong>{" "}
                    {program.notes}
                  </p>
                ) : null}
                {program.days.length === 0 ? (
                  <p className="muted">{t("person.programs.noDays")}</p>
                ) : (
                  program.days.map((day) => (
                    <section
                      key={day.id ?? `${day.day_number}-${day.title}`}
                      className="person-day"
                    >
                      <h3 className="person-day__title">
                        {t("person.programs.day", {
                          day: formatNumber(day.day_number),
                        })}
                        {" · "}
                        {day.title}
                      </h3>
                      {day.weekday ? (
                        <span className="muted person-day__weekday">
                          {t("person.programs.weekday")}:{" "}
                          {t(`weekday.${day.weekday}` as TranslationKey)}
                        </span>
                      ) : null}
                      {day.category_names?.length ? (
                        <div className="row" style={{ gap: 4 }}>
                          {day.category_names.map((name) => (
                            <span key={name} className="m3-chip">
                              {name}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {day.notes ? (
                        <p className="muted person-day__notes">
                          <strong>{t("person.programs.dayNotes")}:</strong>{" "}
                          {day.notes}
                        </p>
                      ) : null}
                      {day.exercises.length === 0 ? (
                        <p className="muted">
                          {t("person.programs.noExercises")}
                        </p>
                      ) : (
                        day.exercises.map((exercise) => (
                          <div
                            key={
                              exercise.id ??
                              `${exercise.order_index}-${exercise.exercise_name}`
                            }
                            className="person-exercise"
                          >
                            <div className="person-exercise__head">
                              <strong>{exercise.exercise_name}</strong>
                              <span className="muted">
                                {exercise.muscle_group}
                              </span>
                            </div>
                            {exercise.notes ? (
                              <p className="muted person-exercise__note">
                                {exercise.notes}
                              </p>
                            ) : null}
                            {exercise.sets.length === 0 ? (
                              <p className="muted">
                                {t("person.programs.noSets")}
                              </p>
                            ) : (
                              <div className="person-set-wrap">
                                <table className="person-set-table">
                                  <thead>
                                    <tr>
                                      <th scope="col">
                                        {t("person.sets.number")}
                                      </th>
                                      <th scope="col">
                                        {t("person.sets.reps")}
                                      </th>
                                      <th scope="col">
                                        {t("person.sets.weight")}
                                      </th>
                                      <th scope="col">
                                        {t("person.sets.rest")}
                                      </th>
                                      <th scope="col">
                                        {t("person.sets.duration")}
                                      </th>
                                      <th scope="col">
                                        {t("person.sets.intensity")}
                                      </th>
                                      <th scope="col">
                                        {t("person.sets.note")}
                                      </th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {exercise.sets.map((set) => (
                                      <tr key={set.set_number}>
                                        <td>{formatNumber(set.set_number)}</td>
                                        <td>
                                          {set.reps_min == null &&
                                          set.reps_max == null
                                            ? "—"
                                            : set.reps_min === set.reps_max
                                              ? formatNumber(set.reps_min)
                                              : `${formatNumber(
                                                  set.reps_min ?? 0,
                                                )}–${formatNumber(
                                                  set.reps_max ?? 0,
                                                )}`}
                                        </td>
                                        <td>
                                          {set.weight_kg == null
                                            ? "—"
                                            : `${formatNumber(
                                                set.weight_kg,
                                              )} ${t("common.units.kg")}`}
                                        </td>
                                        <td>
                                          {set.rest_seconds == null
                                            ? "—"
                                            : `${formatNumber(
                                                set.rest_seconds,
                                              )} ${t("common.units.seconds")}`}
                                        </td>
                                        <td>{set.intensity || "—"}</td>
                                        <td>{set.note || "—"}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        ))
                      )}
                    </section>
                  ))
                )}
              </div>
            </details>
          ))}
        </div>
      </Card>
    )
  }

  if (!gymId) {
    return (
      <PageHeader
        title={t("person.profile.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  if (overviewQuery.isLoading) {
    return <Spinner label={t("common.loading")} />
  }

  if (overviewQuery.isError || !overviewQuery.data) {
    return (
      <ErrorState
        message={translateApiError(overviewQuery.error, t)}
        onRetry={() => overviewQuery.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  const data = overviewQuery.data
  const athlete = data.athlete
  const coach = data.coach
  const kindLabel =
    kind === "ATHLETE" ? t("person.kind.athlete") : t("person.kind.coach")
  const profile = athlete?.profile

  return (
    <div className="person-overview">
      <PageHeader
        title={data.account.full_name ?? data.account.email}
        subtitle={t("person.subtitle", {
          gym: data.focus_gym_name,
          kind: kindLabel,
        })}
        onBack={() => router.history.back()}
        backLabel={t("common.back")}
        actions={
          <Button
            variant="outlined"
            icon={<ExternalLink size={16} />}
            onClick={() => {
              setActiveGym(data.focus_gym_id)
              if (kind === "ATHLETE") {
                navigate({
                  to: "/gyms/$gymId/athletes/$athleteId",
                  params: {
                    gymId: data.focus_gym_id,
                    athleteId: data.account.user_id,
                  },
                })
              } else {
                navigate({
                  to: "/gyms/$gymId/members",
                  params: { gymId: data.focus_gym_id },
                })
              }
            }}
          >
            {t("person.openClubRecord")}
          </Button>
        }
      />

      <section className="m3-profile-hero m3-profile-hero--solo">
        <div className="m3-profile-hero__identity">
          <div className="m3-profile-hero__avatar">
            <Avatar name={data.account.full_name ?? data.account.email} />
          </div>
          <div className="m3-profile-hero__info">
            <div className="m3-profile-hero__name">
              <span className="m3-profile-hero__title">
                {data.account.full_name ?? data.account.email}
              </span>
              <StatusBadge
                status={
                  profile
                    ? profile.is_archived
                      ? "archived"
                      : "active"
                    : coach?.is_active
                      ? "active"
                      : "inactive"
                }
              />
            </div>
            <div className="m3-profile-hero__contacts">
              <a
                className="m3-contact-chip"
                href={`mailto:${data.account.email}`}
                dir="ltr"
              >
                <Mail size={14} aria-hidden />
                <span>{data.account.email}</span>
              </a>
              {data.account.phone ? (
                <a
                  className="m3-contact-chip"
                  href={`tel:${data.account.phone}`}
                  dir="ltr"
                >
                  <Phone size={14} aria-hidden />
                  <span>{data.account.phone}</span>
                </a>
              ) : null}
              <span className="m3-contact-chip">
                <UserRound size={14} aria-hidden />
                <span>
                  {t("context.coach")}:{" "}
                  {athlete?.current_coach?.full_name ??
                    athlete?.current_coach?.email ??
                    t("athletes.noCoach")}
                </span>
              </span>
            </div>
          </div>
        </div>
      </section>

      <div className="person-stats">
        <div className="person-stat">
          <span className="person-stat__value">
            {formatNumber(data.stats.memberships)}
          </span>
          <span className="person-stat__label">
            {t("person.stats.memberships")}
          </span>
        </div>
        <div className="person-stat">
          <span className="person-stat__value">
            {formatNumber(data.stats.assignments)}
          </span>
          <span className="person-stat__label">
            {t("person.stats.assignments")}
          </span>
          <span className="person-stat__hint">
            {t("person.stats.activeAssignments", {
              count: formatNumber(data.stats.active_assignments),
            })}
          </span>
        </div>
        <div className="person-stat">
          <span className="person-stat__value">
            {formatNumber(data.stats.program_versions)}
          </span>
          <span className="person-stat__label">
            {t("person.stats.programs")}
          </span>
        </div>
        <div className="person-stat">
          <span className="person-stat__value">
            {formatNumber(data.stats.body_files)}
          </span>
          <span className="person-stat__label">{t("person.stats.files")}</span>
        </div>
      </div>

      <nav className="person-jumps" aria-label={t("person.jumpTo")}>
        <span className="person-jumps__label">{t("person.jumpTo")}</span>
        <a href="#person-account">{t("person.account.title")}</a>
        {athlete ? (
          <a href="#person-athlete">{t("person.profile.title")}</a>
        ) : null}
        {athlete ? (
          <a href="#person-programs">{t("person.programs.title")}</a>
        ) : null}
        {athlete ? <a href="#person-files">{t("person.files.title")}</a> : null}
        {coach ? <a href="#person-coach">{t("person.coach.title")}</a> : null}
        {coach ? (
          <a href="#person-coach-programs">
            {t("person.programs.authoredTitle")}
          </a>
        ) : null}
        <a href="#person-history">{t("person.history.title")}</a>
      </nav>

      <div className="stack">
        <Card id="person-account">
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("person.account.title")}</h2>
              <p className="m3-section__subtitle">{t("person.account.hint")}</p>
            </div>
            <UserRound size={22} className="muted" aria-hidden />
          </div>
          <div className="grid-2">
            <DetailField label={t("auth.email")}>
              <span dir="ltr">{data.account.email}</span>
            </DetailField>
            <DetailField label={t("profile.phone")}>
              <span dir="ltr">{data.account.phone}</span>
            </DetailField>
            <DetailField label={t("person.account.status")}>
              <StatusBadge
                status={data.account.is_active ? "active" : "inactive"}
              />
            </DetailField>
            <DetailField label={t("person.account.created")}>
              {formatDateTime(data.account.created_at)}
            </DetailField>
          </div>

          <h3 className="person-subheading">{t("person.memberships.title")}</h3>
          <p className="muted person-subheading-hint">
            {t("person.memberships.hint")}
          </p>
          {data.memberships.length === 0 ? (
            <p className="muted">{t("person.memberships.empty")}</p>
          ) : (
            <div className="person-list">
              {data.memberships.map((membership) => (
                <div
                  key={membership.membership_id}
                  className="person-list__item"
                >
                  <Users size={17} className="muted" aria-hidden />
                  <div className="person-list__main">
                    <strong>{membership.gym_name}</strong>
                    <span className="muted">
                      {t("person.memberships.joined")}:{" "}
                      {formatDate(membership.created_at)}
                    </span>
                  </div>
                  <div className="row" style={{ gap: 4 }}>
                    {membership.is_owner ? (
                      <span className="m3-chip">{t("person.owner")}</span>
                    ) : null}
                    {membership.roles.map((role) => (
                      <span key={role} className="m3-chip">
                        {roleLabel(role)}
                      </span>
                    ))}
                    <StatusBadge
                      status={membership.is_active ? "active" : "inactive"}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {athlete ? (
          <>
            <Card id="person-athlete">
              <div className="m3-section__header">
                <div>
                  <h2 className="m3-section__title">
                    {t("person.profile.title")}
                  </h2>
                  <p className="m3-section__subtitle">
                    {t("person.profile.updatedAt")}:{" "}
                    {formatDateTime(profile?.updated_at)}
                  </p>
                </div>
                <Avatar name={profile?.full_name ?? data.account.email} />
              </div>
              <div className="grid-2">
                <DetailField label={t("athletes.fullName")}>
                  {profile?.full_name}
                </DetailField>
                <DetailField label={t("athletes.phone")}>
                  <span dir="ltr">{profile?.phone}</span>
                </DetailField>
                <DetailField label={t("athletes.birthDate")}>
                  {formatDate(profile?.birth_date)}
                </DetailField>
                <DetailField label={t("athletes.fitnessLevel")}>
                  {profile?.fitness_level === "beginner"
                    ? t("athletes.levelBeginner")
                    : profile?.fitness_level === "intermediate"
                      ? t("athletes.levelIntermediate")
                      : profile?.fitness_level === "advanced"
                        ? t("athletes.levelAdvanced")
                        : profile?.fitness_level}
                </DetailField>
                <DetailField label={t("athletes.goal")}>
                  {profile?.training_goal}
                </DetailField>
                <DetailField label={t("athletes.trainingDays")}>
                  {profile?.training_days_count
                    ? formatNumber(profile.training_days_count)
                    : null}
                </DetailField>
                <DetailField label={t("athletes.equipment")}>
                  {profile?.equipment}
                </DetailField>
                <DetailField label={t("person.profile.createdAt")}>
                  {formatDateTime(profile?.created_at)}
                </DetailField>
                {profile?.training_days?.length ? (
                  <DetailField label={t("person.profile.trainingDaysList")}>
                    {profile.training_days
                      .map((day) => t(`weekday.${day}` as TranslationKey))
                      .join(" · ")}
                  </DetailField>
                ) : null}
              </div>
              <div className="grid-2" style={{ marginTop: 14 }}>
                <DetailField label={t("athletes.sportsHistory")}>
                  {profile?.sports_history}
                </DetailField>
                <DetailField label={t("athletes.limitations")}>
                  {profile?.limitations}
                </DetailField>
              </div>
            </Card>

            <Card id="person-measurements">
              <div className="m3-section__header">
                <div>
                  <h2 className="m3-section__title">
                    {t("athletes.measurements")}
                  </h2>
                  <p className="m3-section__subtitle">
                    {t("person.profile.measurementsUpdated")}:{" "}
                    {formatDateTime(athlete.measurements_updated_at)}
                  </p>
                </div>
              </div>
              <div className="grid-3">
                <DetailField label={t("athletes.height")}>
                  {profile?.height_cm != null
                    ? `${formatNumber(profile.height_cm)} ${t(
                        "common.units.cm",
                      )}`
                    : null}
                </DetailField>
                <DetailField label={t("athletes.weight")}>
                  {profile?.weight_kg != null
                    ? `${formatNumber(profile.weight_kg)} ${t(
                        "common.units.kg",
                      )}`
                    : null}
                </DetailField>
                <DetailField label={t("athletes.chest")}>
                  {profile?.chest_cm != null
                    ? `${formatNumber(profile.chest_cm)} ${t(
                        "common.units.cm",
                      )}`
                    : null}
                </DetailField>
                <DetailField label={t("athletes.waist")}>
                  {profile?.waist_cm != null
                    ? `${formatNumber(profile.waist_cm)} ${t(
                        "common.units.cm",
                      )}`
                    : null}
                </DetailField>
                <DetailField label={t("athletes.hips")}>
                  {profile?.hips_cm != null
                    ? `${formatNumber(profile.hips_cm)} ${t("common.units.cm")}`
                    : null}
                </DetailField>
                <DetailField label={t("athletes.arm")}>
                  {profile?.arm_cm != null
                    ? `${formatNumber(profile.arm_cm)} ${t("common.units.cm")}`
                    : null}
                </DetailField>
                <DetailField label={t("athletes.thigh")}>
                  {profile?.thigh_cm != null
                    ? `${formatNumber(profile.thigh_cm)} ${t(
                        "common.units.cm",
                      )}`
                    : null}
                </DetailField>
              </div>
            </Card>

            <Card id="person-note">
              <div className="m3-section__header">
                <div>
                  <h2 className="m3-section__title">
                    {t("athletes.internalNote")}
                  </h2>
                  <p className="m3-section__subtitle">
                    {t("athletes.internalNoteHint")}
                  </p>
                </div>
                <ShieldAlert size={21} className="muted" aria-hidden />
              </div>
              {athlete.internal_coach_note ? (
                <p className="person-note">{athlete.internal_coach_note}</p>
              ) : (
                <p className="muted">{t("person.note.empty")}</p>
              )}
            </Card>

            <Card id="person-assignments">
              <div className="m3-section__header">
                <div>
                  <h2 className="m3-section__title">
                    {t("athletes.assignmentHistory")}
                  </h2>
                  <p className="m3-section__subtitle">
                    {t("person.assignment.historyHint")}
                  </p>
                </div>
                <History size={21} className="muted" aria-hidden />
              </div>
              <div className="person-list">
                <div className="person-list__item">
                  <UserRound size={17} className="muted" aria-hidden />
                  <div className="person-list__main">
                    <strong>{t("person.assignment.current")}</strong>
                    <span className="muted">
                      {athlete.current_coach?.full_name ??
                        athlete.current_coach?.email ??
                        t("athletes.noCoach")}
                    </span>
                  </div>
                </div>
                {athlete.assignments.length === 0 ? (
                  <p className="muted">{t("person.assignment.empty")}</p>
                ) : (
                  athlete.assignments.map(assignmentRow)
                )}
              </div>
            </Card>

            {programsSection({
              programs: athlete.programs,
              title: t("person.programs.title"),
              hint: t("person.programs.hint"),
              emptyTitle: t("person.programs.empty"),
              emptyHint: t("person.programs.emptyHint"),
              id: "person-programs",
            })}

            <Card id="person-files">
              <div className="m3-section__header">
                <div>
                  <h2 className="m3-section__title">
                    {t("person.files.title")}
                  </h2>
                  <p className="m3-section__subtitle">
                    {t("person.files.hint")}
                  </p>
                </div>
                <FileUp size={21} className="muted" aria-hidden />
              </div>
              {athlete.body_files.length === 0 ? (
                <EmptyState
                  icon={<FileUp size={24} />}
                  title={t("person.files.empty")}
                />
              ) : (
                <div className="person-list">
                  {athlete.body_files.map((file) => (
                    <div key={file.id} className="person-list__item">
                      <FileUp size={17} className="muted" aria-hidden />
                      <div className="person-list__main">
                        <strong>{file.original_name}</strong>
                        <span className="muted">
                          {file.gym_name} · {formatBytes(file.size_bytes)} ·{" "}
                          {file.content_type} ·{" "}
                          {formatDateTime(file.created_at)}
                          {file.uploaded_by_name
                            ? ` · ${t("person.files.uploadedBy")}: ${
                                file.uploaded_by_name
                              }`
                            : ""}
                        </span>
                      </div>
                      <Button
                        variant="text"
                        size="sm"
                        icon={<Download size={14} />}
                        onClick={() => downloadFile(file)}
                        aria-label={`${t("common.download")} ${
                          file.original_name
                        }`}
                      >
                        {t("common.download")}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        ) : null}

        {coach ? (
          <Card id="person-coach">
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("person.coach.title")}</h2>
                <p className="m3-section__subtitle">{data.focus_gym_name}</p>
              </div>
              <Users size={22} className="muted" aria-hidden />
            </div>
            <div className="grid-2">
              <DetailField label={t("person.roles")}>
                <span className="row" style={{ gap: 4 }}>
                  {coach.roles.map((role) => (
                    <span key={role} className="m3-chip">
                      {roleLabel(role)}
                    </span>
                  ))}
                </span>
              </DetailField>
              <DetailField label={t("person.coach.status")}>
                <StatusBadge status={coach.is_active ? "active" : "inactive"} />
              </DetailField>
              <DetailField label={t("person.owner")}>
                {coach.is_owner ? t("common.yes") : t("common.no")}
              </DetailField>
              <DetailField label={t("person.stats.assignments")}>
                {formatNumber(coach.assignments.length)}
              </DetailField>
            </div>

            <h3 className="person-subheading">{t("person.coach.athletes")}</h3>
            <p className="muted person-subheading-hint">
              {t("person.coach.athletesHint")}
            </p>
            {coach.assignments.length === 0 ? (
              <p className="muted">{t("person.coach.athletesEmpty")}</p>
            ) : (
              <div className="person-list">
                {coach.assignments.map(assignmentRow)}
              </div>
            )}
          </Card>
        ) : null}

        {coach
          ? programsSection({
              programs: coach.authored_programs,
              title: t("person.programs.authoredTitle"),
              hint: t("person.programs.authoredHint"),
              emptyTitle: t("person.programs.authoredEmpty"),
              emptyHint: t("person.programs.authoredEmptyHint"),
              id: "person-coach-programs",
            })
          : null}

        <Card id="person-history">
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("person.history.title")}</h2>
              <p className="m3-section__subtitle">{t("person.history.hint")}</p>
            </div>
            <History size={22} className="muted" aria-hidden />
          </div>
          {data.history.length === 0 ? (
            <p className="muted">{t("person.history.empty")}</p>
          ) : (
            <ol className="person-timeline">
              {data.history.map((event) => (
                <li
                  key={`${event.event}-${event.related_id}-${event.occurred_at}`}
                  className="person-timeline__item"
                >
                  <span className="person-timeline__dot" aria-hidden />
                  <div className="person-timeline__body">
                    <div className="person-timeline__head">
                      <strong>
                        {t(`person.event.${event.event}` as TranslationKey)}
                      </strong>
                      <time dateTime={event.occurred_at}>
                        {formatDateTime(event.occurred_at)}
                      </time>
                    </div>
                    {eventDescription(event) ? (
                      <p className="person-timeline__detail">
                        {eventDescription(event)}
                      </p>
                    ) : null}
                    <div className="person-timeline__meta">
                      {event.gym_name ? <span>{event.gym_name}</span> : null}
                      {event.actor_name ? (
                        <span>
                          {t("person.history.by", {
                            name: event.actor_name,
                          })}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
          <p className="muted person-history-generated">
            {t("person.history.generatedAt", {
              time: formatDateTime(data.generated_at),
            })}
          </p>
        </Card>
      </div>
    </div>
  )
}
