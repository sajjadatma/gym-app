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

export const MAX_MONEY_IRR = 1_000_000_000_000_000

export type NumericParseFailure = "required" | "invalid" | "precision" | "range"

export type NumericParseResult =
  | { ok: true; value: number }
  | { ok: false; reason: NumericParseFailure }

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

function normalizeFinanceDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String(ARABIC_DIGITS.indexOf(digit)))
}

function parseLocalizedNumber(raw: string): NumericParseResult {
  const trimmed = raw.trim()
  if (!trimmed) return { ok: false, reason: "required" }
  const normalized = normalizeFinanceDigits(trimmed)
    .replace(/[\s\u00a0\u202f]/g, "")
    .replace(/[٬,]/g, "")
    .replace(/٫/g, ".")
    .replace(/^\+/, "")
  if (!/^\d+(?:\.\d+)?$/.test(normalized)) {
    return { ok: false, reason: "invalid" }
  }
  const fraction = normalized.split(".")[1] ?? ""
  if (fraction.length > 2) {
    return { ok: false, reason: "precision" }
  }
  const value = Number(normalized)
  if (!Number.isFinite(value)) return { ok: false, reason: "invalid" }
  return { ok: true, value }
}

/** Parse a Toman form value into the integer IRR convention used by the API. */
export function parseTomanToIrr(raw: string): NumericParseResult {
  const parsed = parseLocalizedNumber(raw)
  if (!parsed.ok) return parsed
  const normalized = normalizeFinanceDigits(raw.trim())
    .replace(/[\s\u00a0\u202f]/g, "")
    .replace(/[٬,]/g, "")
    .replace(/٫/g, ".")
    .replace(/^\+/, "")
  const fraction = normalized.split(".")[1] ?? ""
  if (fraction.length > 1) {
    return { ok: false, reason: "precision" }
  }
  const irr = Math.round(parsed.value * 10)
  if (!Number.isSafeInteger(irr) || irr > MAX_MONEY_IRR) {
    return { ok: false, reason: "range" }
  }
  return { ok: true, value: irr }
}

/** Parse a human percent value into basis points (0..10000). */
export function parsePercentToBp(raw: string): NumericParseResult {
  const parsed = parseLocalizedNumber(raw)
  if (!parsed.ok) return parsed
  if (parsed.value < 0 || parsed.value > 100) {
    return { ok: false, reason: "range" }
  }
  const bp = Math.round(parsed.value * 100)
  if (!Number.isSafeInteger(bp)) return { ok: false, reason: "range" }
  return { ok: true, value: bp }
}

export function tomanToIrr(value: number): number {
  return Math.round(value * 10)
}

export function irrToToman(value: number): number {
  return value / 10
}

/** Exact editable Toman value, preserving the one decimal place IRR allows. */
export function irrToTomanInput(value: number): string {
  return String(value / 10)
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
