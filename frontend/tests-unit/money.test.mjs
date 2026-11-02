import assert from "node:assert/strict"
import test from "node:test"

import {
  formatIrr,
  MAX_FINANCE_IRR,
  normalizeDigits,
  parseAmountInUnit,
  parseIrrInput,
} from "../src/lib/money.js"

const plain = (value) => String(value)

test("persisted IRR stays integer and rial display never rounds", () => {
  assert.equal(formatIrr(0, "RIAL", plain), "0")
  assert.equal(formatIrr(105, "RIAL", plain), "105")
  assert.equal(formatIrr(105, "TOMAN", plain), "10.5")
  assert.equal(formatIrr(100, "TOMAN", plain), "10")
  assert.equal(formatIrr(1_000_000, "TOMAN", plain), "100000")
})

test("toman display keeps a single rial remainder exactly", () => {
  assert.equal(formatIrr(9, "TOMAN", plain), "0.9")
  assert.equal(formatIrr(19, "TOMAN", plain), "1.9")
  assert.equal(formatIrr(999, "TOMAN", plain), "99.9")
  assert.equal(formatIrr(1_000_000_001, "TOMAN", plain), "100000000.1")
})

test("formatting delegates digits and grouping to the locale formatter", () => {
  const persian = (value) => `fa:${value}`
  assert.equal(formatIrr(1230, "RIAL", persian), "fa:1230")
  assert.equal(formatIrr(1235, "TOMAN", persian), "fa:123.fa:5")
})

test("persian and arabic-indic digits are accepted like latin digits", () => {
  assert.equal(normalizeDigits("۱۲۳۴۵۶۷۸۹۰"), "1234567890")
  assert.equal(normalizeDigits("٠١٢٣٤٥٦٧٨٩"), "0123456789")
  assert.equal(parseIrrInput("۱۲۳۴۵"), 12345)
  assert.equal(parseIrrInput("١٢٣٤٥"), 12345)
  assert.equal(parseIrrInput("1,234,567"), 1234567)
  assert.equal(parseIrrInput(" 1 234 "), 1234)
  assert.equal(parseIrrInput("۱۲٬۳۴۵"), 12345)
})

test("invalid or unsafe amounts are rejected instead of rounded", () => {
  assert.equal(parseIrrInput(""), null)
  assert.equal(parseIrrInput("   "), null)
  assert.equal(parseIrrInput("12.5"), null)
  assert.equal(parseIrrInput("۱۲.۵"), null)
  assert.equal(parseIrrInput("-5"), null)
  assert.equal(parseIrrInput("abc"), null)
  assert.equal(parseIrrInput("1e6"), null)
  assert.equal(parseIrrInput(String(MAX_FINANCE_IRR + 1)), null)
  assert.equal(parseIrrInput(String(MAX_FINANCE_IRR)), MAX_FINANCE_IRR)
})

test("large safe amounts keep an exact rial remainder", () => {
  const amount = 999_999_999_999_999
  assert.ok(Number.isSafeInteger(amount))
  assert.equal(formatIrr(amount, "TOMAN", plain), "99999999999999.9")
})

test("amounts typed in the display unit convert to exact integer IRR", () => {
  assert.equal(parseAmountInUnit("1000", "RIAL"), 1000)
  assert.equal(parseAmountInUnit("۱۰۰۰", "RIAL"), 1000)
  assert.equal(parseAmountInUnit("1000", "TOMAN"), 10000)
  assert.equal(parseAmountInUnit("10.5", "TOMAN"), 105)
  assert.equal(parseAmountInUnit("۱۰٫۵", "TOMAN"), 105)
  assert.equal(parseAmountInUnit("10", "TOMAN"), 100)
  assert.equal(parseAmountInUnit("10.55", "TOMAN"), null)
  assert.equal(parseAmountInUnit("10.5", "RIAL"), null)
  assert.equal(parseAmountInUnit("", "TOMAN"), null)
})
