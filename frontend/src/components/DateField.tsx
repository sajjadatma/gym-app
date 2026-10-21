import { jalaaliMonthLength, toGregorian, toJalaali } from "jalaali-js"
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"

import { useI18n } from "../i18n"
import { IconButton } from "./M3"

function pad(value: number) {
  return String(value).padStart(2, "0")
}

function isoFromParts(year: number, month: number, day: number) {
  return `${String(year).padStart(4, "0")}-${pad(month)}-${pad(day)}`
}

function parseIso(value: string): { year: number; month: number; day: number } {
  const [year, month, day] = value.split("-").map(Number)
  return { year, month, day }
}

function todayIso() {
  const now = new Date()
  return isoFromParts(now.getFullYear(), now.getMonth() + 1, now.getDate())
}

export function DateField({
  label,
  value,
  onChange,
  error,
  helper,
  required,
  disabled,
}: {
  label: string
  value: string | null | undefined
  onChange: (value: string | null) => void
  error?: string
  helper?: string
  required?: boolean
  disabled?: boolean
}) {
  const { locale, direction, formatDate, localizeDigits, t } = useI18n()
  const id = useId()
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [view, setView] = useState(() => {
    const base = value ? parseIso(value) : parseIso(todayIso())
    if (locale === "fa") {
      const jalali = toJalaali(base.year, base.month, base.day)
      return { year: jalali.jy, month: jalali.jm }
    }
    return { year: base.year, month: base.month }
  })

  useEffect(() => {
    if (!open) return
    const handleOutside = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", handleOutside)
    return () => document.removeEventListener("mousedown", handleOutside)
  }, [open])

  function openPicker() {
    if (disabled) return
    const base = value ? parseIso(value) : parseIso(todayIso())
    if (locale === "fa") {
      const jalali = toJalaali(base.year, base.month, base.day)
      setView({ year: jalali.jy, month: jalali.jm })
    } else {
      setView({ year: base.year, month: base.month })
    }
    setOpen((current) => !current)
  }

  function moveMonth(delta: number) {
    setView((current) => {
      let month = current.month + delta
      let year = current.year
      if (month < 1) {
        month = 12
        year -= 1
      } else if (month > 12) {
        month = 1
        year += 1
      }
      return { year, month }
    })
  }

  let daysInMonth: number
  let firstWeekday: number
  let monthLabel: string
  let cells: Array<{ day: number; iso: string } | null>

  if (locale === "fa") {
    daysInMonth = jalaaliMonthLength(view.year, view.month)
    const first = toGregorian(view.year, view.month, 1)
    const firstDate = new Date(first.gy, first.gm - 1, first.gd)
    firstWeekday = (firstDate.getDay() + 1) % 7
    monthLabel = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
      year: "numeric",
      month: "long",
    }).format(firstDate)
    cells = Array.from({ length: firstWeekday }).map(() => null)
    for (let day = 1; day <= daysInMonth; day += 1) {
      const gregorian = toGregorian(view.year, view.month, day)
      cells.push({
        day,
        iso: isoFromParts(gregorian.gy, gregorian.gm, gregorian.gd),
      })
    }
  } else {
    const firstDate = new Date(view.year, view.month - 1, 1)
    daysInMonth = new Date(view.year, view.month, 0).getDate()
    firstWeekday = firstDate.getDay()
    monthLabel = new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "long",
    }).format(firstDate)
    cells = Array.from({ length: firstWeekday }).map(() => null)
    for (let day = 1; day <= daysInMonth; day += 1) {
      cells.push({
        day,
        iso: isoFromParts(view.year, view.month, day),
      })
    }
  }

  const weekStart =
    locale === "fa" ? new Date(2024, 0, 6) : new Date(2024, 0, 7)
  const weekdayLabels = Array.from({ length: 7 }).map((_, index) => {
    const date = new Date(weekStart)
    date.setDate(weekStart.getDate() + index)
    return new Intl.DateTimeFormat(locale === "fa" ? "fa-IR" : "en-US", {
      weekday: "narrow",
    }).format(date)
  })

  const selectedIso = value ?? null
  const today = todayIso()

  return (
    <div className="m3-field m3-field--date" ref={wrapperRef}>
      <span className="m3-field__label" id={`${id}-label`}>
        {label}
        {required ? (
          <span className="m3-field__required" aria-hidden>
            *
          </span>
        ) : null}
      </span>
      <button
        type="button"
        className={`m3-field__control m3-field__date-button ${
          error ? "m3-field--error" : ""
        }`}
        onClick={openPicker}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-labelledby={`${id}-label`}
        disabled={disabled}
      >
        <CalendarDays size={19} aria-hidden />
        <span className={selectedIso ? "" : "m3-field__placeholder"}>
          {selectedIso ? formatDate(selectedIso, true) : t("common.selectDate")}
        </span>
      </button>
      {error ? (
        <p className="m3-field__message m3-field__message--error">{error}</p>
      ) : helper ? (
        <p className="m3-field__message">{helper}</p>
      ) : null}
      {open ? (
        <div
          className="m3-date-popover"
          role="dialog"
          aria-modal="false"
          aria-label={label}
        >
          <header className="m3-date-popover__header">
            <IconButton
              label={
                direction === "rtl" ? t("common.next") : t("common.previous")
              }
              onClick={() => moveMonth(direction === "rtl" ? 1 : -1)}
            >
              {direction === "rtl" ? (
                <ChevronRight size={20} />
              ) : (
                <ChevronLeft size={20} />
              )}
            </IconButton>
            <strong>{monthLabel}</strong>
            <IconButton
              label={
                direction === "rtl" ? t("common.previous") : t("common.next")
              }
              onClick={() => moveMonth(direction === "rtl" ? -1 : 1)}
            >
              {direction === "rtl" ? (
                <ChevronLeft size={20} />
              ) : (
                <ChevronRight size={20} />
              )}
            </IconButton>
          </header>
          <div className="m3-date-grid m3-date-grid--head" aria-hidden>
            {weekdayLabels.map((label, index) => (
              <span key={`${label}-${index}`}>{label}</span>
            ))}
          </div>
          <div className="m3-date-grid">
            {cells.map((cell, index) =>
              cell ? (
                <button
                  key={cell.iso}
                  type="button"
                  aria-label={formatDate(cell.iso)}
                  className={`m3-date-day ${
                    cell.iso === selectedIso ? "is-selected" : ""
                  } ${cell.iso === today ? "is-today" : ""}`}
                  onClick={() => {
                    onChange(cell.iso)
                    setOpen(false)
                  }}
                >
                  {localizeDigits(cell.day)}
                </button>
              ) : (
                <span key={`empty-${index}`} />
              ),
            )}
          </div>
          <footer className="m3-date-popover__footer">
            <button
              type="button"
              className="m3-text-button"
              onClick={() => {
                onChange(today)
                setOpen(false)
              }}
            >
              {t("common.today")}
            </button>
            {selectedIso ? (
              <button
                type="button"
                className="m3-text-button"
                onClick={() => {
                  onChange(null)
                  setOpen(false)
                }}
              >
                {t("common.clear")}
              </button>
            ) : null}
          </footer>
        </div>
      ) : null}
    </div>
  )
}
