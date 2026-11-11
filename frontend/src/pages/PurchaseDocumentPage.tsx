import { useQuery } from "@tanstack/react-query"
import { translateApiError } from "@/api"
import {
  Button,
  ErrorState,
  PageHeader,
  SectionCard,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { getPurchaseDocument } from "@/lib/activity-api"
import { formatToman } from "@/lib/finance-ui"

export function PurchaseDocumentPage({
  gymId,
  saleId,
}: {
  gymId: string
  saleId: string
}) {
  const { t, formatNumber, formatDate } = useI18n()
  const query = useQuery({
    queryKey: ["purchase-document", gymId, saleId],
    queryFn: () => getPurchaseDocument(gymId, saleId),
  })
  const money = (value: number) => formatToman(value, formatNumber)
  if (query.isLoading) return <Spinner label={t("common.loading")} />
  if (query.isError || !query.data)
    return (
      <ErrorState
        message={translateApiError(query.error, t)}
        onRetry={() => void query.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  const doc = query.data
  return (
    <article className="m3-purchase-document">
      <div className="m3-document-actions">
        <PageHeader
          title={t("activity.document")}
          actions={
            <Button onClick={() => window.print()}>
              {t("common.print")} / PDF
            </Button>
          }
        />
      </div>
      <SectionCard title={t("activity.invoice")} subtitle={doc.reference}>
        <h2>{doc.gym_name}</h2>
        <p>
          {doc.gym_address} {doc.gym_phone}
        </p>
        <p>
          {t("activity.customer")}: {doc.athlete_name}
        </p>
        <p>
          {t("common.date")}: {formatDate(doc.issued_at)}
        </p>
        <div className="m3-table-wrap">
          <table className="m3-table">
            <thead>
              <tr>
                <th>{t("finance.sales.description")}</th>
                <th>{t("finance.purchase.basePrice")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{doc.description}</td>
                <td>{money(doc.base_amount_irr)}</td>
              </tr>
              {doc.taxes.map((tax, index) => (
                <tr key={`${tax.name}-${index}`}>
                  <td>{tax.name}</td>
                  <td>{money(tax.amount_irr)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th>{t("finance.purchase.total")}</th>
                <td>{money(doc.total_amount_irr)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
        {doc.refunded_irr > 0 ? (
          <p>
            {t("finance.metric.refunds")}: {money(doc.refunded_irr)}
          </p>
        ) : null}
      </SectionCard>
      <SectionCard title={t("activity.receipt")}>
        {doc.payments.length ? (
          doc.payments.map((payment) => (
            <div key={payment.reference} className="stack-sm">
              <strong>{payment.reference}</strong>
              <span>
                {money(payment.amount_irr)} ·{" "}
                {payment.paid_at ? formatDate(payment.paid_at) : "—"}
              </span>
            </div>
          ))
        ) : (
          <p>{t("activity.noReceipt")}</p>
        )}
        <p>{t("activity.documentNote")}</p>
      </SectionCard>
    </article>
  )
}
