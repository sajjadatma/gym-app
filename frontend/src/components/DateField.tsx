import {
  type CalendarDate,
  GregorianCalendar,
  getLocalTimeZone,
  PersianCalendar,
  parseDate,
  toCalendar,
  today,
} from "@internationalized/date"
import {
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
} from "lucide-react"
import { useState } from "react"
import {
  Button as AriaButton,
  Dialog as AriaDialog,
  Select as AriaSelect,
  Calendar,
  CalendarCell,
  CalendarGrid,
  CalendarGridBody,
  CalendarGridHeader,
  CalendarHeaderCell,
  CalendarHeading,
  CalendarMonthPicker,
  CalendarYearPicker,
  DateInput,
  DatePicker,
  DateSegment,
  FieldError,
  Group,
  I18nProvider,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  SelectValue,
  Text,
} from "react-aria-components"

import { useI18n } from "../i18n"
import { useMobileViewport } from "../lib/useMobileViewport"

function CalendarPicker({
  ariaLabel,
  value,
  onChange,
  items,
}: {
  ariaLabel: string
  value: string | number
  onChange: (key: string | number | null) => void
  items: Array<{ id: number; formatted: string }>
}) {
  return (
    <AriaSelect
      value={value}
      onChange={onChange}
      className="m3-calendar__picker"
    >
      <Label className="m3-calendar__picker-label">{ariaLabel}</Label>
      <AriaButton className="m3-calendar__picker-button">
        <SelectValue />
        <ChevronDown size={14} aria-hidden />
      </AriaButton>
      <Popover
        className="m3-calendar__picker-popover"
        offset={4}
        containerPadding={8}
        placement="bottom start"
      >
        <ListBox items={items} className="m3-listbox m3-calendar__picker-list">
          {(item) => (
            <ListBoxItem
              id={item.id}
              textValue={item.formatted}
              className="m3-listbox__item"
            >
              {({ isSelected }) => (
                <>
                  <span className="m3-listbox__indicator" aria-hidden>
                    {isSelected ? <Check size={16} /> : null}
                  </span>
                  <span className="m3-listbox__label">{item.formatted}</span>
                </>
              )}
            </ListBoxItem>
          )}
        </ListBox>
      </Popover>
    </AriaSelect>
  )
}

export function DateField({
  label,
  value,
  onChange,
  error,
  helper,
  required,
  disabled,
  id,
  minValue,
  maxValue,
  maxToday,
}: {
  label: string
  value: string | null | undefined
  onChange: (value: string | null) => void
  error?: string
  helper?: string
  required?: boolean
  disabled?: boolean
  id?: string
  minValue?: string | null
  maxValue?: string | null
  maxToday?: boolean
}) {
  const { locale, direction, t } = useI18n()
  const isMobile = useMobileViewport()
  const [open, setOpen] = useState(false)
  const localeTag =
    locale === "fa" ? "fa-IR-u-ca-persian" : "en-US-u-ca-gregory"
  const calendar =
    locale === "fa" ? new PersianCalendar() : new GregorianCalendar()
  const selected = value ? toCalendar(parseDate(value), calendar) : null
  const todayValue = toCalendar(today(getLocalTimeZone()), calendar)
  const minimum = minValue
    ? toCalendar(parseDate(minValue), calendar)
    : undefined
  const maximum = maxToday
    ? todayValue
    : maxValue
      ? toCalendar(parseDate(maxValue), calendar)
      : undefined
  const canSelectToday =
    (!minimum || todayValue.compare(minimum) >= 0) &&
    (!maximum || todayValue.compare(maximum) <= 0)

  function handleChange(next: CalendarDate | null) {
    if (!next) {
      onChange(null)
      return
    }
    onChange(toCalendar(next, new GregorianCalendar()).toString())
  }

  return (
    <I18nProvider locale={localeTag}>
      <DatePicker
        id={id}
        value={selected}
        onChange={handleChange}
        isOpen={open}
        onOpenChange={setOpen}
        isRequired={required}
        isDisabled={disabled}
        isInvalid={Boolean(error)}
        minValue={minimum}
        maxValue={maximum}
        placeholderValue={todayValue}
        granularity="day"
        firstDayOfWeek={locale === "fa" ? "sat" : "sun"}
        dir={direction}
        className={`m3-field m3-picker-field m3-date-field ${error ? "is-invalid" : ""}`}
      >
        <Label className="m3-field__label">
          {label}
          {required ? (
            <span className="m3-field__required" aria-hidden>
              *
            </span>
          ) : null}
        </Label>
        <Group className="m3-field__control m3-date-field__control">
          <DateInput className="m3-date-field__input">
            {(segment) => (
              <DateSegment segment={segment} className="m3-date-segment" />
            )}
          </DateInput>
          <AriaButton
            className="m3-date-field__trigger"
            aria-label={t("common.selectDate")}
          >
            <CalendarDays size={19} aria-hidden />
          </AriaButton>
        </Group>
        <FieldError className="m3-field__message m3-field__message--error">
          {error}
        </FieldError>
        {!error && helper ? (
          <Text slot="description" className="m3-field__message">
            {helper}
          </Text>
        ) : null}
        <Popover
          className="m3-date-popover"
          offset={8}
          containerPadding={12}
          placement={isMobile ? "top start" : "bottom start"}
        >
          <AriaDialog className="m3-date-dialog" aria-label={label}>
            <Calendar
              aria-label={label}
              firstDayOfWeek={locale === "fa" ? "sat" : "sun"}
            >
              <CalendarHeading className="sr-only" />
              <header className="m3-calendar__header">
                <AriaButton
                  slot="previous"
                  className="m3-calendar__nav"
                  aria-label={t("common.previous")}
                >
                  {direction === "rtl" ? (
                    <ChevronRight size={20} aria-hidden />
                  ) : (
                    <ChevronLeft size={20} aria-hidden />
                  )}
                </AriaButton>
                <div className="m3-calendar__pickers">
                  <CalendarMonthPicker>
                    {(props) => (
                      <CalendarPicker
                        ariaLabel={props["aria-label"]}
                        value={props.value}
                        onChange={props.onChange}
                        items={props.items}
                      />
                    )}
                  </CalendarMonthPicker>
                  <CalendarYearPicker visibleYears={100}>
                    {(props) => (
                      <CalendarPicker
                        ariaLabel={props["aria-label"]}
                        value={props.value}
                        onChange={props.onChange}
                        items={props.items}
                      />
                    )}
                  </CalendarYearPicker>
                </div>
                <AriaButton
                  slot="next"
                  className="m3-calendar__nav"
                  aria-label={t("common.next")}
                >
                  {direction === "rtl" ? (
                    <ChevronLeft size={20} aria-hidden />
                  ) : (
                    <ChevronRight size={20} aria-hidden />
                  )}
                </AriaButton>
              </header>
              <CalendarGrid className="m3-calendar__grid">
                <CalendarGridHeader>
                  {(day) => (
                    <CalendarHeaderCell className="m3-calendar__weekday">
                      {day}
                    </CalendarHeaderCell>
                  )}
                </CalendarGridHeader>
                <CalendarGridBody>
                  {(date) => (
                    <CalendarCell
                      date={date}
                      className={({ isSelected, isOutsideMonth }) =>
                        `m3-calendar__day ${
                          isSelected ? "is-selected" : ""
                        } ${isOutsideMonth ? "is-outside-month" : ""} ${
                          date.compare(todayValue) === 0 ? "is-today" : ""
                        }`
                      }
                    />
                  )}
                </CalendarGridBody>
              </CalendarGrid>
              <footer className="m3-calendar__actions">
                <button
                  type="button"
                  className="m3-text-button"
                  disabled={!canSelectToday}
                  onClick={() => {
                    handleChange(todayValue)
                    setOpen(false)
                  }}
                >
                  {t("common.today")}
                </button>
                {value ? (
                  <button
                    type="button"
                    className="m3-text-button"
                    onClick={() => {
                      handleChange(null)
                      setOpen(false)
                    }}
                  >
                    {t("common.clear")}
                  </button>
                ) : null}
              </footer>
            </Calendar>
          </AriaDialog>
        </Popover>
      </DatePicker>
    </I18nProvider>
  )
}
