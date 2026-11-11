import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  CalendarDays,
  ClipboardList,
  Printer,
  ShoppingBag,
  UserRound,
} from "lucide-react"
import { useState } from "react"
import { getApiErrorDetail, translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { AthletesService, ProgramsService } from "@/client"
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
  StatusBadge,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import {
  getTrainingOffer,
  listAthleteProgramRequests,
  purchaseTrainingPlan,
  type TrainingOffer,
} from "@/lib/finance-api"
import { formatToman } from "@/lib/finance-ui"
import { useSnackbar } from "@/snackbar"

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
  const offerQuery = useQuery({
    queryKey: ["finance-training-offer", activeGymId],
    queryFn: () => getTrainingOffer(activeGymId!),
    enabled: Boolean(activeGymId && activeRole === "ATHLETE"),
  })
  const requestsQuery = useQuery({
    queryKey: ["finance-athlete-requests", activeGymId],
    queryFn: () => listAthleteProgramRequests(activeGymId!),
    enabled: Boolean(activeGymId && activeRole === "ATHLETE"),
  })
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [purchaseOpen, setPurchaseOpen] = useState(false)
  const [purchaseOffer, setPurchaseOffer] = useState<TrainingOffer | null>(null)
  const [purchaseKey, setPurchaseKey] = useState("")
  const [purchaseNote, setPurchaseNote] = useState("")
  const [purchaseError, setPurchaseError] = useState<string | null>(null)
  const [purchasing, setPurchasing] = useState(false)

  function openPurchase() {
    setPurchaseOffer(offerQuery.data ?? null)
    setPurchaseKey(crypto.randomUUID())
    setPurchaseNote("")
    setPurchaseError(null)
    setPurchaseOpen(true)
  }

  async function buyPlan() {
    const offer = purchaseOffer
    if (!offer) return
    setPurchasing(true)
    setPurchaseError(null)
    try {
      const result = await purchaseTrainingPlan(activeGymId!, {
        plan_id: offer.plan.id,
        quote_token: offer.quote_token,
        note: purchaseNote.trim() || null,
        idempotency_key: purchaseKey,
      })
      if (!result.request) {
        setPurchaseError(t("finance.purchase.failed"))
        return
      }
      await queryClient.invalidateQueries({
        queryKey: ["finance-athlete-requests", activeGymId],
      })
      setPurchaseOpen(false)
      show(t("finance.purchase.success"), "success")
    } catch (err) {
      if (getApiErrorDetail(err) === "training_quote_changed") {
        const refreshed = await offerQuery.refetch()
        setPurchaseOffer(refreshed.isError ? null : (refreshed.data ?? null))
        setPurchaseKey(crypto.randomUUID())
        setPurchaseError(
          refreshed.isError
            ? translateApiError(refreshed.error, t)
            : t("activity.quoteChanged"),
        )
      } else {
        setPurchaseError(translateApiError(err, t))
      }
    } finally {
      setPurchasing(false)
    }
  }

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
              onClick={() =>
                window.open(`/print/${active.id}?gym=${activeGymId}`, "_blank")
              }
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

      <Card>
        <div className="m3-section__header">
          <div>
            <h2 className="m3-section__title">{t("finance.purchase.title")}</h2>
            <p className="m3-section__subtitle">
              {t("finance.purchase.subtitle")}
            </p>
          </div>
          <ShoppingBag size={22} className="muted" />
        </div>
        {offerQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : offerQuery.isError ? (
          <ErrorState
            message={translateApiError(offerQuery.error, t)}
            onRetry={() => void offerQuery.refetch()}
            retryLabel={t("common.retry")}
          />
        ) : offerQuery.data ? (
          <div className="stack-sm">
            <div className="row row--between">
              <strong>{offerQuery.data.plan.title}</strong>
              <span className="m3-status m3-status--active">
                {formatToman(offerQuery.data.total_amount_irr, formatNumber)}
              </span>
            </div>
            {offerQuery.data.plan.description ? (
              <p className="muted" style={{ fontSize: 13 }}>
                {offerQuery.data.plan.description}
              </p>
            ) : null}
            <div className="m3-entity-card__meta">
              <span>
                {t("finance.purchase.basePrice")}:{" "}
                {formatToman(offerQuery.data.plan.base_price_irr, formatNumber)}
              </span>
              <span>
                {t("finance.purchase.tax")}:{" "}
                {formatToman(offerQuery.data.tax_amount_irr, formatNumber)}
              </span>
              <span>
                {t("finance.purchase.coach")}:{" "}
                {offerQuery.data.plan.coach_name ?? "—"}
              </span>
            </div>
            <div className="row">
              <Button onClick={openPurchase}>
                {t("finance.purchase.buy")}
              </Button>
            </div>
          </div>
        ) : (
          <p className="muted" style={{ fontSize: 13 }}>
            {t("finance.purchase.unavailable")}
          </p>
        )}
        {requestsQuery.isError ? (
          <ErrorState
            message={translateApiError(requestsQuery.error, t)}
            onRetry={() => void requestsQuery.refetch()}
            retryLabel={t("common.retry")}
          />
        ) : null}
        {requestsQuery.data?.length ? (
          <div className="stack-sm" style={{ marginTop: 18 }}>
            <h3 className="m3-section__title">
              {t("finance.purchase.myRequests")}
            </h3>
            {requestsQuery.data.map((request) => (
              <div key={request.id} className="m3-version-row">
                <div className="m3-version-row__main">
                  <ClipboardList size={18} className="muted" />
                  <div>
                    <div className="m3-version-row__title">
                      {request.plan_title}
                    </div>
                    <div className="m3-version-row__meta">
                      {formatDate(request.created_at)} ·{" "}
                      {formatToman(request.total_amount_irr, formatNumber)}
                    </div>
                  </div>
                </div>
                <span className="m3-status">
                  {request.status === "REQUESTED"
                    ? t("finance.requests.statusRequested")
                    : request.status === "IN_PROGRESS"
                      ? t("activity.preparing")
                      : request.status === "FULFILLED"
                        ? t("finance.requests.statusFulfilled")
                        : t("finance.requests.statusCancelled")}
                </span>
                <div className="row" style={{ flexWrap: "wrap" }}>
                  <Button
                    variant="text"
                    onClick={() =>
                      navigate({
                        to: "/gyms/$gymId/my/purchases/$saleId",
                        params: {
                          gymId: activeGymId!,
                          saleId: request.sale_id,
                        },
                      })
                    }
                  >
                    {t("activity.document")}
                  </Button>
                  {request.status === "FULFILLED" &&
                  request.program_version_id &&
                  request.program_status !== "DRAFT" ? (
                    <Button
                      variant="text"
                      onClick={() =>
                        navigate({
                          to: "/gyms/$gymId/my/programs/$versionId",
                          params: {
                            gymId: activeGymId!,
                            versionId: request.program_version_id!,
                          },
                        })
                      }
                    >
                      {t("activity.viewProgram")}
                    </Button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </Card>

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

      <Dialog
        open={purchaseOpen}
        title={t("finance.purchase.dialogTitle")}
        dismissible={!purchasing}
        onClose={() => setPurchaseOpen(false)}
        footer={
          <>
            <Button
              variant="text"
              onClick={() => setPurchaseOpen(false)}
              disabled={purchasing}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={() => void buyPlan()}
              loading={purchasing}
              disabled={!purchaseOffer}
            >
              {t("finance.purchase.pay")}
            </Button>
          </>
        }
      >
        {purchaseOffer ? (
          <div className="stack-sm">
            <strong>{purchaseOffer.plan.title}</strong>
            <div className="m3-entity-card__meta">
              <span>
                {t("finance.purchase.basePrice")}:{" "}
                {formatToman(purchaseOffer.plan.base_price_irr, formatNumber)}
              </span>
              <span>
                {t("finance.purchase.tax")}:{" "}
                {formatToman(purchaseOffer.tax_amount_irr, formatNumber)}
              </span>
              <span>
                {t("finance.purchase.total")}:{" "}
                {formatToman(purchaseOffer.total_amount_irr, formatNumber)}
              </span>
            </div>
            <TextField
              label={t("finance.purchase.noteLabel")}
              value={purchaseNote}
              onChange={(event) => setPurchaseNote(event.target.value)}
              multiline
              helper={t("finance.purchase.noteHint")}
            />
            <p className="m3-field__message">
              {t("finance.purchase.simulation")}
            </p>
          </div>
        ) : null}
        {purchaseError ? (
          <ErrorState
            message={purchaseError}
            onRetry={
              !purchaseOffer
                ? async () => {
                    const fresh = await offerQuery.refetch()
                    setPurchaseOffer(
                      fresh.isError ? null : (fresh.data ?? null),
                    )
                    setPurchaseError(
                      fresh.isError
                        ? translateApiError(fresh.error, t)
                        : t("activity.quoteChanged"),
                    )
                  }
                : undefined
            }
            retryLabel={t("common.retry")}
          />
        ) : null}
      </Dialog>
    </>
  )
}
