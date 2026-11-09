import { useQuery } from "@tanstack/react-query"
import { FlaskConical, ShieldCheck, Wallet } from "lucide-react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  EmptyState,
  ErrorState,
  PageHeader,
  SectionCard,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { getReport } from "@/lib/finance-api"
import { daysAgoIso, formatToman, todayIso } from "@/lib/finance-ui"

type Props = { gymId?: string }

export function FinanceOverviewPage({ gymId }: Props) {
  const { t, formatNumber, formatDate } = useI18n()
  const { isSuperuser, activeGym } = useAuth()
  const from = daysAgoIso(29)
  const to = todayIso()
  const report = useQuery({
    queryKey: ["finance-overview", gymId, from, to],
    queryFn: () => getReport({ gym_id: gymId, from_date: from, to_date: to }),
  })
  const title = gymId
    ? t("finance.overview.gymTitle")
    : t("finance.overview.globalTitle")
  const subtitle = gymId
    ? t("finance.overview.gymSubtitle", { gym: activeGym?.name ?? "" })
    : t("finance.overview.globalSubtitle")

  if (report.isLoading) return <Spinner label={t("common.loading")} />
  if (report.isError) {
    return (
      <ErrorState
        message={translateApiError(report.error, t)}
        onRetry={() => void report.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }
  if (!report.data) return <EmptyState title={t("finance.overview.empty")} />

  const activity = report.data.activity
  const asOf = report.data.as_of

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={
          <span className="m3-simulation-badge">
            <FlaskConical size={16} aria-hidden />
            {t("finance.simulationBadge")}
          </span>
        }
      />
      <div className="m3-finance-note">
        <ShieldCheck size={18} aria-hidden />
        <span>{t("finance.overview.testNote")}</span>
      </div>
      <SectionCard
        title={t("finance.reports.activityTitle")}
        subtitle={t("finance.reports.activitySubtitle", {
          from: formatDate(from),
          to: formatDate(to),
        })}
      >
        <div className="m3-stat-grid">
          <Stat
            label={t("finance.metric.baseSales")}
            value={activity.base_sales_irr}
          />
          <Stat label={t("finance.metric.taxes")} value={activity.taxes_irr} />
          <Stat
            label={t("finance.metric.totalPayments")}
            value={activity.total_payments_irr}
            primary
          />
          <Stat
            label={t("finance.metric.platformShare")}
            value={activity.platform_share_irr}
          />
          <Stat
            label={t("finance.metric.gymShare")}
            value={activity.gym_share_irr}
          />
          <Stat
            label={t("finance.metric.coachShare")}
            value={activity.coach_share_irr}
          />
          <Stat
            label={t("finance.metric.refunds")}
            value={activity.refunds_irr}
          />
          <Stat
            label={t("finance.metric.completedSettlements")}
            value={activity.completed_settlements_irr}
          />
        </div>
      </SectionCard>
      <SectionCard
        title={t("finance.overview.asOfTitle")}
        subtitle={t("finance.overview.asOfSubtitle", {
          date: formatDate(report.data.as_of.date),
        })}
      >
        <div className="m3-stat-grid">
          <Stat
            label={t("finance.metric.unsettledPlatform")}
            value={asOf.unsettled_platform_irr}
          />
          <Stat
            label={t("finance.metric.unsettledGym")}
            value={asOf.unsettled_gym_irr}
          />
          <Stat
            label={t("finance.metric.unsettledCoach")}
            value={asOf.unsettled_coach_irr}
          />
          <Stat
            label={t("finance.metric.pendingSettlements")}
            value={asOf.pending_settlements_irr}
          />
          <Stat
            label={t("finance.metric.completedSettlementsAsOf")}
            value={asOf.completed_settlements_irr}
          />
        </div>
      </SectionCard>
      {isSuperuser && !gymId ? (
        <SectionCard
          title={t("finance.overview.byGym")}
          subtitle={t("finance.overview.byGymSubtitle")}
        >
          {report.data.by_gym.length === 0 ? (
            <EmptyState
              icon={<Wallet size={24} />}
              title={t("finance.overview.noGyms")}
              description={t("finance.overview.noGymsHint")}
            />
          ) : (
            <div className="m3-table-wrap">
              <table className="m3-table">
                <thead>
                  <tr>
                    <th>{t("finance.table.gym")}</th>
                    <th>{t("finance.metric.baseSales")}</th>
                    <th>{t("finance.metric.totalPayments")}</th>
                    <th>{t("finance.metric.platformShare")}</th>
                    <th>{t("finance.metric.gymShare")}</th>
                    <th>{t("finance.metric.coachShare")}</th>
                    <th>{t("finance.metric.pendingSettlements")}</th>
                  </tr>
                </thead>
                <tbody>
                  {report.data.by_gym.map((row) => (
                    <tr key={row.gym_id}>
                      <td>{row.gym_name}</td>
                      <td>
                        {formatToman(row.activity.base_sales_irr, formatNumber)}
                      </td>
                      <td>
                        {formatToman(
                          row.activity.total_payments_irr,
                          formatNumber,
                        )}
                      </td>
                      <td>
                        {formatToman(
                          row.activity.platform_share_irr,
                          formatNumber,
                        )}
                      </td>
                      <td>
                        {formatToman(row.activity.gym_share_irr, formatNumber)}
                      </td>
                      <td>
                        {formatToman(
                          row.activity.coach_share_irr,
                          formatNumber,
                        )}
                      </td>
                      <td>
                        {formatToman(
                          row.as_of.pending_settlements_irr,
                          formatNumber,
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      ) : null}
    </div>
  )
}

function Stat({
  label,
  value,
  primary = false,
}: {
  label: string
  value: number
  primary?: boolean
}) {
  const { formatNumber } = useI18n()
  return (
    <div className={`m3-stat ${primary ? "m3-stat--primary" : ""}`}>
      <span className="m3-stat__label">{label}</span>
      <strong className="m3-stat__value">
        {formatToman(value, formatNumber)}
      </strong>
    </div>
  )
}
