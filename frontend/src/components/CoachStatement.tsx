import { useQuery } from "@tanstack/react-query"
import { translateApiError } from "@/api"
import {
  Card,
  EmptyState,
  ErrorState,
  SectionCard,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { getCoachStatement } from "@/lib/activity-api"
import { formatToman } from "@/lib/finance-ui"

export function CoachStatement({ gymId }: { gymId: string }) {
  const { t, formatNumber, formatDate } = useI18n()
  const query = useQuery({
    queryKey: ["coach-statement", gymId],
    queryFn: () => getCoachStatement(gymId),
  })
  const money = (value: number) => formatToman(value, formatNumber)
  return (
    <SectionCard
      title={t("activity.statement")}
      subtitle={t("activity.statementNote")}
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
              [t("activity.earned"), query.data.earned_irr],
              [t("activity.refunded"), query.data.refunded_irr],
              [t("activity.available"), query.data.available_irr],
              [t("activity.pending"), query.data.pending_irr],
              [t("activity.paid"), query.data.settled_irr],
            ].map(([label, value]) => (
              <Card key={String(label)}>
                <div className="m3-stat__label">{label}</div>
                <strong>{money(Number(value))}</strong>
              </Card>
            ))}
          </div>
          {query.data.post_settlement_adjustments_irr > 0 ? (
            <p role="status">
              {t("activity.adjustment")}:{" "}
              {money(query.data.post_settlement_adjustments_irr)}
            </p>
          ) : null}
          {query.data.entries.length ? (
            <div className="m3-table-wrap">
              <table className="m3-table">
                <caption>{t("activity.earningsHistory")}</caption>
                <thead>
                  <tr>
                    <th>{t("common.date")}</th>
                    <th>{t("finance.sales.description")}</th>
                    <th>{t("activity.earned")}</th>
                    <th>{t("activity.refunded")}</th>
                    <th>{t("activity.available")}</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.entries.map((entry) => (
                    <tr key={entry.id}>
                      <td>{formatDate(entry.created_at)}</td>
                      <td>{entry.description}</td>
                      <td>{money(entry.earned_irr)}</td>
                      <td>{money(entry.refunded_irr)}</td>
                      <td>{money(entry.available_irr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title={t("activity.noEarnings")} />
          )}
          {query.data.settlements.length ? (
            <div className="m3-table-wrap">
              <table className="m3-table">
                <caption>{t("activity.settlements")}</caption>
                <thead>
                  <tr>
                    <th>{t("common.date")}</th>
                    <th>{t("finance.table.amount")}</th>
                    <th>{t("finance.table.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.settlements.map((row) => (
                    <tr key={row.id}>
                      <td>{formatDate(row.requested_at)}</td>
                      <td>{money(row.amount_irr)}</td>
                      <td>
                        {t(
                          row.status === "COMPLETED"
                            ? "activity.paid"
                            : row.status === "PENDING"
                              ? "activity.pending"
                              : "activity.cancelled",
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </SectionCard>
  )
}
