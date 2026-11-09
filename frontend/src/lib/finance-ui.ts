import type { FinanceCategory, SettlementParty } from "./finance-api"

export const CATEGORY_LABELS: Record<FinanceCategory, string> = {
  MEMBERSHIP: "حق عضویت باشگاه",
  NUTRITION: "برنامه تغذیه",
  TRAINING: "برنامه تمرینی",
}

export const PARTY_LABELS: Record<SettlementParty, string> = {
  PLATFORM: "سهم پلتفرم",
  GYM: "سهم باشگاه",
  COACH: "سهم مربی",
}

export const STATUS_LABELS: Record<string, string> = {
  DRAFT: "پیش‌نویس",
  ACTIVE: "فعال",
  ARCHIVED: "بایگانی‌شده",
  AWAITING_PAYMENT: "در انتظار پرداخت",
  PAID: "پرداخت‌شده",
  PARTIALLY_REFUNDED: "بازگشت وجه جزئی",
  REFUNDED: "بازگشت وجه کامل",
  CANCELLED: "لغوشده",
  SUCCEEDED: "موفق",
  FAILED: "ناموفق",
  PENDING: "در انتظار تسویه",
  COMPLETED: "تسویه‌شده",
  SUCCESS: "موفق",
  FAILURE: "ناموفق",
  CANCELLATION: "لغو",
}

export function categoryLabel(category: FinanceCategory): string {
  return CATEGORY_LABELS[category]
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? "وضعیت نامشخص"
}

export function partyLabel(party: SettlementParty): string {
  return PARTY_LABELS[party]
}

export function sourceLabel(source: string): string {
  return source === "GYM_OVERRIDE"
    ? "درصد اختصاصی این باشگاه"
    : "درصد پیش‌فرض پلتفرم"
}

export function tomanToIrr(value: number): number {
  return Math.round(value * 10)
}

export function irrToToman(value: number): number {
  return Math.round(value / 10)
}

export function formatToman(
  irr: number | null | undefined,
  formatNumber: (value: number | string | null | undefined) => string,
): string {
  if (irr === null || irr === undefined) return "—"
  return `${formatNumber(irrToToman(irr))} تومان`
}

export function percentFromBp(bp: number): string {
  return (bp / 100).toLocaleString("fa-IR", { maximumFractionDigits: 2 })
}

export function bpFromPercent(value: number): number {
  return Math.round(value * 100)
}

export function todayIso(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(
    now.getDate(),
  ).padStart(2, "0")}`
}

export function daysAgoIso(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`
}
