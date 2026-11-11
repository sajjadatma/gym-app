import type { TranslationKey } from "@/i18n"

import type { NumericParseResult } from "./finance-ui"

type Translator = (key: TranslationKey) => string

export function parseErrorMessage(
  result: NumericParseResult,
  kind: "amount" | "percent",
  t: Translator,
): string | undefined {
  if (result.ok) return undefined
  if (kind === "percent") {
    if (result.reason === "precision") {
      return t("finance.validation.percentPrecision")
    }
    if (result.reason === "range") {
      return t("finance.validation.percentRange")
    }
    return t("finance.validation.percentInvalid")
  }
  if (result.reason === "required") {
    return t("finance.validation.amountRequired")
  }
  if (result.reason === "precision") {
    return t("finance.validation.amountPrecision")
  }
  if (result.reason === "range") {
    return t("finance.validation.amountRange")
  }
  return t("finance.validation.amountInvalid")
}
