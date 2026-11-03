import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { FinanceService } from "@/client"
import { ErrorState, PageHeader, Spinner, Tabs } from "@/components/M3"
import { useI18n } from "@/i18n"
import { FinanceCatalogSection } from "./finance/FinanceCatalogSection"
import { FinanceCoachesSection } from "./finance/FinanceCoachesSection"
import { FinanceExpensesSection } from "./finance/FinanceExpensesSection"
import { FinanceInvoicesSection } from "./finance/FinanceInvoicesSection"
import { FinanceMembershipsSection } from "./finance/FinanceMembershipsSection"
import { FinanceOverviewSection } from "./finance/FinanceOverviewSection"
import { FinancePaymentsSection } from "./finance/FinancePaymentsSection"
import { FinancePlatformSection } from "./finance/FinancePlatformSection"
import { FinanceRefundsSection } from "./finance/FinanceRefundsSection"

export function FinancePage() {
  const { t } = useI18n()
  const { activeGymId, activeGym } = useAuth()
  const [tab, setTab] = useState("overview")

  const scope = activeGymId ?? ""
  const settingsQuery = useQuery({
    queryKey: ["finance", scope, "settings"],
    queryFn: async () => (await FinanceService.readFinanceSettings()).data,
    enabled: Boolean(activeGymId),
    retry: false,
  })

  if (!activeGymId || !activeGym) {
    return (
      <PageHeader
        title={t("finance.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  if (settingsQuery.isLoading) return <Spinner label={t("common.loading")} />
  if (settingsQuery.isError) {
    return (
      <ErrorState
        message={translateApiError(settingsQuery.error, t)}
        retryLabel={t("common.retry")}
        onRetry={() => settingsQuery.refetch()}
      />
    )
  }

  const settings = settingsQuery.data!
  const unit = settings.display_unit

  return (
    <>
      <PageHeader
        title={t("finance.title")}
        subtitle={`${activeGym.name} · ${t("finance.subtitle")}`}
        actions={
          <span className="m3-chip">
            {settings.enabled ? t("finance.enabled") : t("finance.readOnly")}
          </span>
        }
      />

      {!settings.enabled ? (
        <div className="m3-inline-alert" role="status">
          {t("finance.disabledHint")}
        </div>
      ) : null}

      <Tabs
        value={tab}
        onChange={setTab}
        idPrefix="finance-tabs"
        tabs={[
          { value: "overview", label: t("finance.tabOverview") },
          { value: "invoices", label: t("finance.tabInvoices") },
          { value: "catalog", label: t("finance.tabCatalog") },
          { value: "payments", label: t("finance.tabPayments") },
          { value: "refunds", label: t("finance.tabRefunds") },
          { value: "expenses", label: t("finance.tabExpenses") },
          { value: "memberships", label: t("finance.tabMemberships") },
          { value: "coaches", label: t("finance.tabCoaches") },
          { value: "platform", label: t("finance.tabPlatform") },
        ]}
      />

      <div
        role="tabpanel"
        id={`finance-tabs-panel-${tab}`}
        aria-labelledby={`finance-tabs-tab-${tab}`}
        style={{ paddingTop: 16 }}
      >
        {tab === "overview" ? (
          <FinanceOverviewSection settings={settings} unit={unit} />
        ) : tab === "invoices" ? (
          <FinanceInvoicesSection settings={settings} unit={unit} />
        ) : tab === "catalog" ? (
          <FinanceCatalogSection settings={settings} unit={unit} />
        ) : tab === "payments" ? (
          <FinancePaymentsSection settings={settings} unit={unit} />
        ) : tab === "refunds" ? (
          <FinanceRefundsSection settings={settings} unit={unit} />
        ) : tab === "expenses" ? (
          <FinanceExpensesSection settings={settings} unit={unit} />
        ) : tab === "memberships" ? (
          <FinanceMembershipsSection settings={settings} unit={unit} />
        ) : tab === "coaches" ? (
          <FinanceCoachesSection settings={settings} unit={unit} />
        ) : (
          <FinancePlatformSection />
        )}
      </div>
    </>
  )
}
