import { client } from "@/client/client.gen"

const api = client.instance

export type FinanceCategory = "MEMBERSHIP" | "NUTRITION" | "TRAINING"
export type ContractStatus = "DRAFT" | "ACTIVE" | "ARCHIVED"
export type TaxCalculation = "PERCENT" | "FIXED"
export type PaymentOutcome = "SUCCESS" | "FAILURE" | "CANCELLATION"
export type SettlementParty = "PLATFORM" | "GYM" | "COACH"

export type PlatformRate = {
  category: FinanceCategory
  percent_bp: number
}

export type PlatformContract = {
  id: string
  name: string
  scope: "DEFAULT" | "GYM"
  gym_id: string | null
  version: number
  status: ContractStatus
  effective_from: string
  effective_to: string | null
  rates: PlatformRate[]
  activated_at: string | null
  created_at: string
}

export type PlatformPolicy = {
  gym_id: string
  category: FinanceCategory
  on_date: string
  platform_bp: number
  source: string
  contract_id: string
  contract_version: number
}

export type TaxDefinition = {
  id: string
  name: string
  calculation: TaxCalculation
  percent_bp: number | null
  fixed_amount_irr: number | null
  is_active: boolean
  is_default_vat: boolean
}

export type TaxLine = {
  name: string
  calculation: TaxCalculation
  percent_bp: number | null
  fixed_amount_irr: number | null
  amount_irr: number
}

export type CoachContract = {
  id: string
  gym_id: string
  coach_user_id: string
  coach_name: string | null
  category: FinanceCategory
  version: number
  status: ContractStatus
  effective_from: string
  effective_to: string | null
  platform_bp: number
  gym_bp: number
  coach_bp: number
  platform_source: string
  platform_contract_id: string
  activated_at: string | null
  created_at: string
}

export type CoachOption = {
  user_id: string
  name: string
  email: string
}

export type SalePreview = {
  gym_id: string
  category: FinanceCategory
  base_amount_irr: number
  taxes: TaxLine[]
  tax_amount_irr: number
  total_amount_irr: number
  platform_bp: number
  gym_bp: number
  coach_bp: number
  platform_amount_irr: number
  gym_amount_irr: number
  coach_amount_irr: number
  coach_user_id: string | null
  platform_source: string
  platform_contract_id: string
  platform_contract_version: number
  coach_contract_id: string | null
  coach_contract_version: number | null
}

export type Sale = {
  id: string
  gym_id: string
  category: FinanceCategory
  description: string
  sold_on: string
  base_amount_irr: number
  taxes: TaxLine[]
  tax_amount_irr: number
  total_amount_irr: number
  status: string
  platform_bp: number
  gym_bp: number
  coach_bp: number
  platform_amount_irr: number
  gym_amount_irr: number
  coach_amount_irr: number
  coach_user_id: string | null
  coach_name: string | null
  coach_contract_id: string | null
  platform_contract_id: string
  platform_source: string
  refunded_irr: number
  payment_status: string | null
  created_at: string
}

export type Allocation = {
  id: string
  party: SettlementParty
  party_user_id: string | null
  party_name: string | null
  amount_irr: number
  refunded_irr: number
  settled_irr: number
}

export type Payment = {
  id: string
  sale_id: string
  gym_id: string
  amount_irr: number
  status: "SUCCEEDED" | "FAILED" | "CANCELLED"
  outcome: PaymentOutcome
  note: string | null
  paid_at: string | null
  created_at: string
  allocations: Allocation[]
}

export type Settlement = {
  id: string
  gym_id: string
  party: SettlementParty
  party_user_id: string | null
  party_name: string | null
  amount_irr: number
  status: "PENDING" | "COMPLETED" | "CANCELLED"
  requested_at: string
  completed_at: string | null
  cancelled_at: string | null
  items: { allocation_id: string; party: SettlementParty; amount_irr: number }[]
}

export type Refund = {
  id: string
  payment_id: string
  sale_id: string
  amount_irr: number
  status: string
  reason: string
  created_at: string
  adjustments: {
    allocation_id: string
    settlement_id: string | null
    party: SettlementParty
    amount_irr: number
  }[]
}

export type ReportActivity = {
  base_sales_irr: number
  taxes_irr: number
  total_payments_irr: number
  platform_share_irr: number
  gym_share_irr: number
  coach_share_irr: number
  refunds_irr: number
  completed_settlements_irr: number
}

export type ReportAsOf = {
  date: string
  unsettled_platform_irr: number
  unsettled_gym_irr: number
  unsettled_coach_irr: number
  pending_settlements_irr: number
  completed_settlements_irr: number
}

export type Report = {
  gym_id: string | null
  from_date: string
  to_date: string
  activity: ReportActivity
  as_of: ReportAsOf
  by_gym: {
    gym_id: string
    gym_name: string
    activity: ReportActivity
    as_of: ReportAsOf
  }[]
}

export type AuditEntry = {
  id: string
  actor_id: string | null
  actor_name: string | null
  action: string
  entity_type: string
  entity_id: string | null
  detail: Record<string, unknown>
  created_at: string
}

export async function listPlatformContracts(params?: {
  scope?: string
  gym_id?: string
}) {
  return (
    await api.get<PlatformContract[]>("/api/v1/finance/platform-contracts", {
      params,
    })
  ).data
}

export async function createPlatformContract(body: {
  name: string
  scope: "DEFAULT" | "GYM"
  gym_id?: string | null
  effective_from: string
  effective_to?: string | null
  rates: PlatformRate[]
}) {
  return (
    await api.post<PlatformContract>("/api/v1/finance/platform-contracts", body)
  ).data
}

export async function activatePlatformContract(id: string) {
  return (
    await api.post<PlatformContract>(
      `/api/v1/finance/platform-contracts/${id}/activate`,
    )
  ).data
}

export async function archivePlatformContract(id: string) {
  return (
    await api.post<PlatformContract>(
      `/api/v1/finance/platform-contracts/${id}/archive`,
    )
  ).data
}

export async function getPlatformPolicy(
  gymId: string,
  category: FinanceCategory,
  onDate: string,
) {
  return (
    await api.get<PlatformPolicy>("/api/v1/finance/platform-policy", {
      params: { gym_id: gymId, category, on_date: onDate },
    })
  ).data
}

export async function listTaxes(includeInactive = false) {
  return (
    await api.get<TaxDefinition[]>("/api/v1/finance/taxes", {
      params: { include_inactive: includeInactive },
    })
  ).data
}

export async function createTax(body: {
  name: string
  calculation: TaxCalculation
  percent_bp?: number | null
  fixed_amount_irr?: number | null
  is_active?: boolean
  is_default_vat?: boolean
}) {
  return (await api.post<TaxDefinition>("/api/v1/finance/taxes", body)).data
}

export async function updateTax(
  id: string,
  body: {
    name?: string
    calculation?: TaxCalculation
    percent_bp?: number | null
    fixed_amount_irr?: number | null
    is_active?: boolean
    is_default_vat?: boolean
  },
) {
  return (await api.patch<TaxDefinition>(`/api/v1/finance/taxes/${id}`, body))
    .data
}

export async function listCoachContracts(gymId: string) {
  return (
    await api.get<CoachContract[]>(
      `/api/v1/finance/gyms/${gymId}/coach-contracts`,
    )
  ).data
}

export async function createCoachContract(
  gymId: string,
  body: {
    coach_user_id: string
    category: FinanceCategory
    effective_from: string
    effective_to?: string | null
    platform_bp: number
    gym_bp: number
    coach_bp: number
  },
) {
  return (
    await api.post<CoachContract>(
      `/api/v1/finance/gyms/${gymId}/coach-contracts`,
      body,
    )
  ).data
}

export async function activateCoachContract(gymId: string, id: string) {
  return (
    await api.post<CoachContract>(
      `/api/v1/finance/gyms/${gymId}/coach-contracts/${id}/activate`,
    )
  ).data
}

export async function archiveCoachContract(gymId: string, id: string) {
  return (
    await api.post<CoachContract>(
      `/api/v1/finance/gyms/${gymId}/coach-contracts/${id}/archive`,
    )
  ).data
}

export async function listGymCoaches(gymId: string) {
  return (await api.get<CoachOption[]>(`/api/v1/finance/gyms/${gymId}/coaches`))
    .data
}

export async function previewSale(
  gymId: string,
  body: {
    category: FinanceCategory
    base_amount_irr: number
    tax_ids: string[]
    coach_user_id?: string | null
    sold_on: string
  },
) {
  return (
    await api.post<SalePreview>(
      `/api/v1/finance/gyms/${gymId}/sales/preview`,
      body,
    )
  ).data
}

export async function createSale(
  gymId: string,
  body: {
    category: FinanceCategory
    description: string
    base_amount_irr: number
    tax_ids: string[]
    coach_user_id?: string | null
    sold_on: string
  },
) {
  return (await api.post<Sale>(`/api/v1/finance/gyms/${gymId}/sales`, body))
    .data
}

export async function listSales(
  gymId: string,
  params?: {
    from_date?: string
    to_date?: string
    category?: string
    status?: string
  },
) {
  return (
    await api.get<Sale[]>(`/api/v1/finance/gyms/${gymId}/sales`, { params })
  ).data
}

export async function getSale(gymId: string, saleId: string) {
  return (await api.get<Sale>(`/api/v1/finance/gyms/${gymId}/sales/${saleId}`))
    .data
}

export async function simulatePayment(
  gymId: string,
  saleId: string,
  body: { outcome: PaymentOutcome; idempotency_key: string; note?: string },
) {
  return (
    await api.post<Payment>(
      `/api/v1/finance/gyms/${gymId}/sales/${saleId}/payments`,
      body,
    )
  ).data
}

export async function listPayments(gymId: string) {
  return (await api.get<Payment[]>(`/api/v1/finance/gyms/${gymId}/payments`))
    .data
}

export async function createRefund(
  gymId: string,
  paymentId: string,
  body: { amount_irr: number; idempotency_key: string; reason: string },
) {
  return (
    await api.post<Refund>(
      `/api/v1/finance/gyms/${gymId}/payments/${paymentId}/refunds`,
      body,
    )
  ).data
}

export async function listSettlements(gymId: string) {
  return (
    await api.get<Settlement[]>(`/api/v1/finance/gyms/${gymId}/settlements`)
  ).data
}

export async function createSettlement(
  gymId: string,
  body: {
    party: SettlementParty
    party_user_id?: string | null
    amount_irr: number
    idempotency_key: string
  },
) {
  return (
    await api.post<Settlement>(
      `/api/v1/finance/gyms/${gymId}/settlements`,
      body,
    )
  ).data
}

export async function completeSettlement(gymId: string, id: string) {
  return (
    await api.post<Settlement>(
      `/api/v1/finance/gyms/${gymId}/settlements/${id}/complete`,
    )
  ).data
}

export async function cancelSettlement(gymId: string, id: string) {
  return (
    await api.post<Settlement>(
      `/api/v1/finance/gyms/${gymId}/settlements/${id}/cancel`,
    )
  ).data
}

export async function autoSettle(gymId: string) {
  return (
    await api.post<Settlement[]>(
      `/api/v1/finance/gyms/${gymId}/settlements/auto`,
    )
  ).data
}

export async function getReport(params: {
  gym_id?: string
  from_date: string
  to_date: string
  category?: string
}) {
  return (await api.get<Report>("/api/v1/finance/reports", { params })).data
}

export async function downloadReportCsv(params: {
  gym_id?: string
  from_date: string
  to_date: string
  category?: string
}) {
  const response = await api.get<string>("/api/v1/finance/reports/export", {
    params,
    responseType: "text",
  })
  const blob = new Blob([response.data], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "finance-report.csv"
  link.click()
  URL.revokeObjectURL(url)
}

export async function listAudit(gymId: string) {
  return (await api.get<AuditEntry[]>(`/api/v1/finance/gyms/${gymId}/audit`))
    .data
}
