export type MoneyDisplayUnit = "RIAL" | "TOMAN"

export declare const MAX_FINANCE_IRR: number

export declare function normalizeDigits(value: string | number): string

export declare function parseIrrInput(value: string): number | null

export declare function irrInUnit(
  irr: number,
  unit: MoneyDisplayUnit,
): { whole: number; fraction: number }

export declare function formatIrr(
  irr: number,
  unit: MoneyDisplayUnit,
  formatNumber: (value: number | string | null | undefined) => string,
): string

export declare function parseAmountInUnit(
  value: string,
  unit: MoneyDisplayUnit,
): number | null
