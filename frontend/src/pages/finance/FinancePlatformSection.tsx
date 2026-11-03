import { useQuery } from "@tanstack/react-query"
import { Landmark } from "lucide-react"
import { translateApiError } from "@/api"
import { FinanceService } from "@/client"
import {
  Card,
  EmptyState,
  ErrorState,
  SectionCard,
  Spinner,
} from "@/components/M3"
import { useI18n } from "@/i18n"

export function FinancePlatformSection() {
  const { t, formatNumber, formatDate } = useI18n()
  const invoices = useQuery({
    queryKey: ["finance", "platform", "invoices"],
    queryFn: async () =>
      (await FinanceService.readMyGymPlatformInvoices()).data.data,
  })
  const dues = useQuery({
    queryKey: ["finance", "platform", "dues"],
    queryFn: async () => (await FinanceService.readMyGymPlatformDues()).data,
  })
  const payments = useQuery({
    queryKey: ["finance", "platform", "payments"],
    queryFn: async () =>
      (await FinanceService.readMyGymPlatformPayments()).data.data,
  })
  if (invoices.isLoading || dues.isLoading || payments.isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (invoices.isError || dues.isError || payments.isError) {
    return (
      <ErrorState
        message={translateApiError(
          invoices.error ?? dues.error ?? payments.error,
          t,
        )}
        retryLabel={t("common.retry")}
        onRetry={() => {
          void invoices.refetch()
          void dues.refetch()
          void payments.refetch()
        }}
      />
    )
  }
  return (
    <div className="stack">
      <SectionCard title={t("platform.invoices")}>
        {(invoices.data ?? []).length === 0 ? (
          <EmptyState
            icon={<Landmark size={24} />}
            title={t("platform.empty")}
          />
        ) : (
          (invoices.data ?? []).map((invoice) => (
            <Card variant="outlined" key={invoice.id}>
              <div className="row row--between">
                <span>#{formatNumber(invoice.invoice_number)}</span>
                <span>
                  {invoice.status} · {formatNumber(invoice.total_irr)} ·{" "}
                  {formatNumber(invoice.balance_irr)}
                </span>
              </div>
              <div className="muted">{formatDate(invoice.due_on)}</div>
            </Card>
          ))
        )}
      </SectionCard>
      <SectionCard title={t("platform.dues")}>
        <div className="row row--between">
          <span>{dues.data?.stage}</span>
          <span>
            {formatNumber(dues.data?.open_irr ?? 0)} ·{" "}
            {formatNumber(dues.data?.overdue_irr ?? 0)}
          </span>
        </div>
      </SectionCard>
      <SectionCard title={t("platform.reminders")}>
        {(payments.data ?? []).length === 0 ? (
          <EmptyState
            icon={<Landmark size={24} />}
            title={t("platform.empty")}
          />
        ) : (
          (payments.data ?? []).map((payment) => (
            <div className="row row--between" key={payment.id}>
              <span>{formatDate(payment.received_on)}</span>
              <span>{formatNumber(payment.amount_irr)}</span>
            </div>
          ))
        )}
      </SectionCard>
    </div>
  )
}
