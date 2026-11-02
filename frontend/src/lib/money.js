// Integer-rial money helpers. Amounts are persisted as integer IRR and only
// converted for display, so nothing here may round a non-multiple-of-10 rial.

export const MAX_FINANCE_IRR = 10 ** 15

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

/** Convert Persian/Arabic-Indic digits to latin digits. */
export function normalizeDigits(value) {
  return String(value ?? "")
    .replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String(ARABIC_DIGITS.indexOf(digit)))
}

/**
 * Parse a user-typed IRR amount. Returns null for anything that is not a
 * whole, non-negative, JavaScript-safe integer within the finance bound.
 */
export function parseIrrInput(value) {
  const normalized = normalizeDigits(value).replace(/[,\u066c\s\u200c]/g, "")
  if (!/^\d+$/.test(normalized)) return null
  const amount = Number(normalized)
  if (!Number.isSafeInteger(amount) || amount > MAX_FINANCE_IRR) return null
  return amount
}

/** Whole/fraction parts for toman display; 105 IRR is 10.5 toman, never 11. */
export function irrInUnit(irr, unit) {
  if (unit !== "TOMAN") return { whole: irr, fraction: 0 }
  const whole = Math.trunc(irr / 10)
  return { whole, fraction: Math.abs(irr % 10) }
}

/** Format an integer IRR amount for display, delegating digits to the locale. */
export function formatIrr(irr, unit, formatNumber) {
  const { whole, fraction } = irrInUnit(irr, unit)
  const wholeText = formatNumber(whole)
  if (fraction === 0) return wholeText
  return `${wholeText}.${formatNumber(fraction)}`
}

function bounded(amount) {
  return Number.isSafeInteger(amount) &&
    amount >= 0 &&
    amount <= MAX_FINANCE_IRR
    ? amount
    : null
}

/**
 * Parse an amount typed in the display unit into integer IRR. Toman input
 * accepts at most one decimal place, and 0.1 toman is exactly 1 rial.
 */
export function parseAmountInUnit(value, unit) {
  const normalized = normalizeDigits(value).replace(/[,\u066c\s\u200c]/g, "")
  if (!normalized) return null
  if (unit !== "TOMAN") {
    return /^\d+$/.test(normalized) ? bounded(Number(normalized)) : null
  }
  const match = /^(\d+)(?:[.٫](\d)?)?$/.exec(normalized)
  if (!match) return null
  const toman = Number(match[1])
  if (!Number.isSafeInteger(toman)) return null
  const fraction = match[2] ? Number(match[2]) : 0
  return bounded(toman * 10 + fraction)
}
