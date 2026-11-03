import { useQuery } from "@tanstack/react-query"
import { HandCoins, Wallet } from "lucide-react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { FinanceService } from "@/client"
import {
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionCard,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { methodLabel, useMoney } from "./finance/shared"

export function CoachEarningsPage() {
  const { t, formatDate, formatNumber } = useI18n()
  const { activeGym, activeGymId, activeRole } = useAuth()
  const { money } = useMoney("RIAL")

  const earningsQuery = useQuery({
    queryKey: ["finance", activeGymId, "my-coach-earnings"],
    queryFn: async () => (await FinanceService.readMyCoachEarnings()).data,
    enabled: Boolean(activeGymId && activeRole === "COACH"),
  })
  const settlementsQuery = useQuery({
    queryKey: ["finance", activeGymId, "my-coach-settlements"],
    queryFn: async () => (await FinanceService.readMyCoachSettlements()).data,
    enabled: Boolean(activeGymId && activeRole === "COACH"),
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("finance.my.earnings")}
        subtitle={t("context.noGymHint")}
      />
    )
  }
  if (activeRole !== "COACH") {
    return (
      <>
        <PageHeader
          title={t("finance.my.earnings")}
          subtitle={t("finance.my.earningsSubtitle")}
        />
        <ErrorState message={t("errors.coach_access_required")} />
      </>
    )
  }
  if (earningsQuery.isLoading || settlementsQuery.isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (earningsQuery.isError || settlementsQuery.isError) {
    return (
      <ErrorState
        message={translateApiError(
          earningsQuery.error ?? settlementsQuery.error,
          t,
        )}
        retryLabel={t("common.retry")}
        onRetry={() => {
          void earningsQuery.refetch()
          void settlementsQuery.refetch()
        }}
      />
    )
  }

  const earnings = earningsQuery.data?.data ?? []
  const settlements = settlementsQuery.data?.data ?? []
  const totals = earnings.reduce(
    (sum, row) => ({
      calculated: sum.calculated + row.calculated_irr,
      vested: sum.vested + row.vested_irr,
      eligible: sum.eligible + row.eligible_irr,
      settled: sum.settled + row.settled_irr,
    }),
    { calculated: 0, vested: 0, eligible: 0, settled: 0 },
  )

  return (
    <>
      <PageHeader
        title={t("finance.my.earnings")}
        subtitle={`${activeGym.name} · ${t("finance.my.earningsSubtitle")}`}
      />

      <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
        <Card variant="outlined">
          <div className="m3-entity-card__meta">
            <Wallet size={16} />
            <span>{t("finance.coaches.calculated")}</span>
          </div>
          <strong>{money(totals.calculated)}</strong>
        </Card>
        <Card variant="outlined">
          <div className="m3-entity-card__meta">
            <HandCoins size={16} />
            <span>{t("finance.coaches.vestedAmount")}</span>
          </div>
          <strong>{money(totals.vested)}</strong>
        </Card>
        <Card variant="outlined">
          <div className="m3-entity-card__meta">
            <HandCoins size={16} />
            <span>{t("finance.coaches.eligible")}</span>
          </div>
          <strong>{money(totals.eligible)}</strong>
        </Card>
        <Card variant="outlined">
          <div className="m3-entity-card__meta">
            <span>{t("finance.coaches.settled")}</span>
          </div>
          <strong>{money(totals.settled)}</strong>
        </Card>
      </div>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.my.earnings")}
        subtitle={t("finance.coaches.earningsHint")}
      >
        {earnings.length === 0 ? (
          <EmptyState
            icon={<HandCoins size={24} />}
            title={t("finance.my.earningsEmpty")}
          />
        ) : (
          <div className="stack">
            {earnings.map((earning) => (
              <Card key={earning.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>
                      {t("finance.invoice.number")}{" "}
                      {earning.invoice_number
                        ? formatNumber(earning.invoice_number)
                        : "—"}
                    </strong>
                    <div className="m3-entity-card__meta">
                      <span>{earning.line_description}</span>
                      <span className="m3-chip">{earning.status}</span>
                      {earning.vesting_date ? (
                        <span>{formatDate(earning.vesting_date)}</span>
                      ) : null}
                    </div>
                  </div>
                  <div style={{ textAlign: "end" }}>
                    <div>
                      {t("finance.coaches.calculated")}:{" "}
                      {money(earning.calculated_irr)}
                    </div>
                    <div className="muted">
                      {t("finance.coaches.vestedAmount")}:{" "}
                      {money(earning.vested_irr)}
                    </div>
                    <div className="muted">
                      {t("finance.coaches.eligible")}:{" "}
                      {money(earning.eligible_irr)}
                    </div>
                    <div className="muted">
                      {t("finance.coaches.settled")}:{" "}
                      {money(earning.settled_irr)}
                    </div>
                    {(earning.reserved_irr ?? 0) > 0 ? (
                      <div className="muted">
                        {t("finance.coaches.reserved")}:{" "}
                        {money(earning.reserved_irr ?? 0)}
                      </div>
                    ) : null}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <div style={{ height: 16 }} />

      <SectionCard
        title={t("finance.my.settlements")}
        subtitle={t("finance.coaches.settlementsHint")}
      >
        {settlements.length === 0 ? (
          <p className="muted">{t("finance.my.noSettlements")}</p>
        ) : (
          <div className="stack">
            {settlements.map((settlement) => (
              <Card key={settlement.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>{money(settlement.amount_irr)}</strong>
                    <div className="m3-entity-card__meta">
                      <span>{formatDate(settlement.paid_on)}</span>
                      <span className="m3-chip">{settlement.status}</span>
                      <span>{methodLabel(t, settlement.method)}</span>
                      {settlement.reference ? (
                        <span>{settlement.reference}</span>
                      ) : null}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>
    </>
  )
}
