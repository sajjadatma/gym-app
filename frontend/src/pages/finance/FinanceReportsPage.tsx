import { useQuery } from "@tanstack/react-query"
import { BarChart3, Download } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { DateField } from "@/components/DateField"
import {
  Button,
  ErrorState,
  PageHeader,
  SectionCard,
  SelectField,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { downloadReportCsv, getReport } from "@/lib/finance-api"
import {
  categoryLabel,
  daysAgoIso,
  formatToman,
  todayIso,
} from "@/lib/finance-ui"

export function FinanceReportsPage({ gymId }: { gymId?: string }) {
  const { t, formatNumber } = useI18n()
  const { gyms, isSuperuser } = useAuth()
  const [gymFilter, setGymFilter] = useState("")
  const [fromDate, setFromDate] = useState(daysAgoIso(29))
  const [toDate, setToDate] = useState(todayIso())
  const [category, setCategory] = useState("")
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const report = useQuery({
    queryKey: ["finance-report", gymId, gymFilter, fromDate, toDate, category],
    queryFn: () =>
      getReport({
        gym_id: gymId ?? (gymFilter || undefined),
        from_date: fromDate,
        to_date: toDate,
        category: category || undefined,
      }),
  })

  async function exportCsv() {
    setDownloading(true)
    setError(null)
    try {
      await downloadReportCsv({
        gym_id: gymId ?? (gymFilter || undefined),
        from_date: fromDate,
        to_date: toDate,
        category: category || undefined,
      })
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={t("finance.reports.title")}
        subtitle={t("finance.reports.subtitle")}
        actions={
          <Button
            variant="outlined"
            icon={<Download size={16} />}
            onClick={() => void exportCsv()}
            loading={downloading}
          >
            {t("finance.reports.export")}
          </Button>
        }
      />
      <div className="m3-finance-note">
        <BarChart3 size={18} aria-hidden />
        <span>{t("finance.reports.note")}</span>
      </div>
      <SectionCard>
        <div className="m3-filter-bar">
          <DateField
            label={t("finance.reports.from")}
            value={fromDate}
            onChange={(value) => value && setFromDate(value)}
          />
          <DateField
            label={t("finance.reports.to")}
            value={toDate}
            onChange={(value) => value && setToDate(value)}
          />
          {!gymId && isSuperuser ? (
            <SelectField
              label={t("finance.table.gym")}
              value={gymFilter}
              onChange={setGymFilter}
              options={[
                { value: "", label: t("common.all") },
                ...gyms.map((gym) => ({ value: gym.id, label: gym.name })),
              ]}
            />
          ) : null}
          <SelectField
            label={t("finance.table.category")}
            value={category}
            onChange={setCategory}
            options={[
              { value: "", label: t("common.all") },
              { value: "MEMBERSHIP", label: categoryLabel("MEMBERSHIP") },
              { value: "NUTRITION", label: categoryLabel("NUTRITION") },
              { value: "TRAINING", label: categoryLabel("TRAINING") },
            ]}
          />
        </div>
      </SectionCard>
      {error ? <ErrorState message={error} /> : null}
      {report.isLoading ? (
        <Spinner label={t("common.loading")} />
      ) : report.isError ? (
        <ErrorState
          message={translateApiError(report.error, t)}
          onRetry={() => void report.refetch()}
          retryLabel={t("common.retry")}
        />
      ) : report.data ? (
        <>
          <SectionCard
            title={t("finance.reports.activityTitle")}
            subtitle={t("finance.reports.activitySubtitle", {
              from: report.data.from_date,
              to: report.data.to_date,
            })}
          >
            <div className="m3-stat-grid">
              <Stat
                label={t("finance.metric.baseSales")}
                value={report.data.activity.base_sales_irr}
              />
              <Stat
                label={t("finance.metric.taxes")}
                value={report.data.activity.taxes_irr}
              />
              <Stat
                label={t("finance.metric.totalPayments")}
                value={report.data.activity.total_payments_irr}
                primary
              />
              <Stat
                label={t("finance.metric.platformShare")}
                value={report.data.activity.platform_share_irr}
              />
              <Stat
                label={t("finance.metric.gymShare")}
                value={report.data.activity.gym_share_irr}
              />
              <Stat
                label={t("finance.metric.coachShare")}
                value={report.data.activity.coach_share_irr}
              />
              <Stat
                label={t("finance.metric.refunds")}
                value={report.data.activity.refunds_irr}
              />
              <Stat
                label={t("finance.metric.completedSettlements")}
                value={report.data.activity.completed_settlements_irr}
              />
            </div>
          </SectionCard>
          <SectionCard
            title={t("finance.reports.asOfTitle")}
            subtitle={t("finance.reports.asOfSubtitle", {
              date: report.data.as_of.date,
            })}
          >
            <div className="m3-stat-grid">
              <Stat
                label={t("finance.metric.unsettledPlatform")}
                value={report.data.as_of.unsettled_platform_irr}
              />
              <Stat
                label={t("finance.metric.unsettledGym")}
                value={report.data.as_of.unsettled_gym_irr}
              />
              <Stat
                label={t("finance.metric.unsettledCoach")}
                value={report.data.as_of.unsettled_coach_irr}
              />
              <Stat
                label={t("finance.metric.pendingSettlements")}
                value={report.data.as_of.pending_settlements_irr}
              />
              <Stat
                label={t("finance.metric.completedSettlementsAsOf")}
                value={report.data.as_of.completed_settlements_irr}
              />
            </div>
          </SectionCard>
          {report.data.by_gym.length ? (
            <SectionCard title={t("finance.overview.byGym")}>
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
                    </tr>
                  </thead>
                  <tbody>
                    {report.data.by_gym.map((row) => (
                      <tr key={row.gym_id}>
                        <td>{row.gym_name}</td>
                        <td>
                          {formatToman(
                            row.activity.base_sales_irr,
                            formatNumber,
                          )}
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
                          {formatToman(
                            row.activity.gym_share_irr,
                            formatNumber,
                          )}
                        </td>
                        <td>
                          {formatToman(
                            row.activity.coach_share_irr,
                            formatNumber,
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          ) : null}
        </>
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
