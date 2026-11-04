import { useQuery } from "@tanstack/react-query"
import { useAuth } from "@/auth"
import {
  type FinanceCatalogItemPublic,
  type FinanceCustomerPublic,
  FinanceService,
  type FinanceSettingsPublic,
} from "@/client"
import { type TranslationKey, useI18n } from "@/i18n"
import { formatIrr, parseAmountInUnit } from "@/lib/money"

type TFunction = (
  key: TranslationKey,
  values?: Record<string, string | number>,
) => string

export type FinanceSettings = FinanceSettingsPublic

export type FinanceSectionProps = {
  settings: FinanceSettingsPublic
  unit: "RIAL" | "TOMAN"
}

export type FinanceLineKind = FinanceCatalogItemPublic["kind"]

export function todayIso() {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export function addDaysIso(value: string, days: number) {
  const date = new Date(`${value}T00:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export function newKey() {
  return `finance-${Math.random().toString(36).slice(2, 11)}`
}

export function methodLabel(t: TFunction, method: string | null | undefined) {
  switch (method) {
    case "CASH":
      return t("finance.methodCash")
    case "POS":
      return t("finance.methodPos")
    case "TRANSFER":
      return t("finance.methodTransfer")
    default:
      return method ?? "—"
  }
}

export function lineKindLabel(t: TFunction, kind: string) {
  switch (kind) {
    case "MEMBERSHIP":
      return t("finance.invoice.kindMembership")
    case "PROGRAM":
      return t("finance.invoice.kindProgram")
    case "SESSION":
      return t("finance.invoice.kindSession")
    case "PACK":
      return t("finance.invoice.kindPack")
    case "PRODUCT":
      return t("finance.invoice.kindProduct")
    case "SERVICE":
      return t("finance.invoice.kindService")
    default:
      return t("finance.invoice.kindCustom")
  }
}

export function invoiceStatusLabel(t: TFunction, status: string) {
  switch (status) {
    case "DRAFT":
      return t("finance.invoice.draft")
    case "ISSUED":
      return t("finance.invoice.issued")
    case "VOID":
      return t("finance.invoice.void")
    default:
      return status
  }
}

export function refundStatusLabel(t: TFunction, status: string) {
  switch (status) {
    case "REQUESTED":
      return t("finance.refund.statusRequested")
    case "APPROVED":
      return t("finance.refund.statusApproved")
    case "RECORDED":
      return t("finance.refund.statusRecorded")
    case "REJECTED":
      return t("finance.refund.statusRejected")
    default:
      return status
  }
}

export function membershipStatusLabel(t: TFunction, status: string) {
  switch (status) {
    case "ACTIVE":
      return t("finance.membership.active")
    case "FROZEN":
      return t("finance.membership.frozen")
    case "CANCELLED":
      return t("finance.membership.cancelled")
    case "EXPIRED":
      return t("finance.membership.expired")
    default:
      return status
  }
}

/** Render an integer IRR amount as a plain input value in the display unit. */
export function amountInput(irr: number, unit: "RIAL" | "TOMAN") {
  if (unit !== "TOMAN") return String(irr)
  const whole = Math.trunc(irr / 10)
  const fraction = Math.abs(irr % 10)
  return fraction === 0 ? String(whole) : `${whole}.${fraction}`
}

export function useMoney(unit: "RIAL" | "TOMAN") {
  const { t, formatNumber } = useI18n()
  const unitLabel = t(
    unit === "RIAL" ? "finance.unitRial" : "finance.unitToman",
  )
  return {
    unitLabel,
    money: (amount: number) =>
      `${formatIrr(amount, unit, formatNumber)} ${unitLabel}`,
    parse: (value: string) => parseAmountInUnit(value, unit),
  }
}

export function useFinanceCustomers() {
  const { activeGymId } = useAuth()
  const query = useQuery({
    queryKey: ["finance", activeGymId, "customers"],
    queryFn: async () =>
      (await FinanceService.readFinanceCustomers()).data.data,
    enabled: Boolean(activeGymId),
  })
  const customers = query.data ?? []
  return {
    ...query,
    customers,
    customerOptions: customers.map((member) => ({
      value: member.user_id,
      label: member.full_name ?? member.email,
    })),
    coachOptions: customers
      .filter((member) => member.roles.includes("COACH"))
      .map((member) => ({
        value: member.user_id,
        label: member.full_name ?? member.email,
      })),
    customerName: (userId: string | null | undefined) => {
      const member = customers.find(
        (item: FinanceCustomerPublic) => item.user_id === userId,
      )
      return member?.full_name ?? member?.email ?? userId ?? "—"
    },
  }
}
