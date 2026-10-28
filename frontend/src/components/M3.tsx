import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  Search,
  X,
} from "lucide-react"
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type RefObject,
  type TextareaHTMLAttributes,
  useEffect,
  useId,
  useRef,
  useState,
} from "react"
import {
  Button as AriaButton,
  ComboBox as AriaComboBox,
  Input as AriaInput,
  Label as AriaLabel,
  Popover as AriaPopover,
  Select as AriaSelect,
  Text as AriaText,
  FieldError,
  Group,
  I18nProvider,
  ListBox,
  ListBoxItem,
  SelectValue,
} from "react-aria-components"
import { createPortal } from "react-dom"

import { useI18n } from "../i18n"
import { useMobileViewport } from "../lib/useMobileViewport"

type ButtonVariant = "filled" | "tonal" | "outlined" | "text" | "danger"
type ButtonSize = "sm" | "md"

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: ReactNode
  loading?: boolean
  fullWidth?: boolean
}

export function Button({
  variant = "filled",
  size = "md",
  icon,
  loading,
  fullWidth,
  className = "",
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      className={`m3-button m3-button--${variant} m3-button--${size} ${
        fullWidth ? "m3-button--full" : ""
      } ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="m3-spinner m3-spinner--small" aria-hidden />
      ) : (
        icon
      )}
      {children ? <span>{children}</span> : null}
    </button>
  )
}

export function IconButton({
  label,
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string
}) {
  return (
    <button
      type="button"
      className={`m3-icon-button ${className}`}
      aria-label={label}
      title={label}
      {...props}
    >
      {children}
    </button>
  )
}

export function Card({
  children,
  className = "",
  variant = "filled",
  id,
}: {
  children: ReactNode
  className?: string
  variant?: "filled" | "outlined" | "plain"
  id?: string
}) {
  return (
    <section id={id} className={`m3-card m3-card--${variant} ${className}`}>
      {children}
    </section>
  )
}

export function SectionCard({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={className}>
      {title || actions ? (
        <header className="m3-section__header">
          <div>
            {title ? <h2 className="m3-section__title">{title}</h2> : null}
            {subtitle ? (
              <p className="m3-section__subtitle">{subtitle}</p>
            ) : null}
          </div>
          {actions ? (
            <div className="m3-section__actions">{actions}</div>
          ) : null}
        </header>
      ) : null}
      {children}
    </Card>
  )
}

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "size"> & {
  label: string
  error?: string
  helper?: string
  multiline?: boolean
  rows?: number
  suffix?: string
  leading?: ReactNode
  trailing?: ReactNode
  containerClassName?: string
}

export function TextField({
  label,
  error,
  helper,
  multiline,
  rows = 4,
  suffix,
  leading,
  trailing,
  containerClassName = "",
  className = "",
  id,
  required,
  "aria-describedby": describedBy,
  ...props
}: TextFieldProps) {
  const generatedId = useId()
  const fieldId = id ?? generatedId
  const messageId = `${fieldId}-message`
  const description =
    [describedBy, error || helper ? messageId : undefined]
      .filter(Boolean)
      .join(" ") || undefined
  const inputClasses = `m3-field__input ${className}`
  return (
    <div
      className={`m3-field ${error ? "m3-field--error" : ""} ${containerClassName}`}
    >
      <label className="m3-field__label" htmlFor={fieldId}>
        {label}
        {required ? (
          <span className="m3-field__required" aria-hidden>
            *
          </span>
        ) : null}
      </label>
      <div className="m3-field__control">
        {leading ? <span className="m3-field__leading">{leading}</span> : null}
        {multiline ? (
          <textarea
            id={fieldId}
            className={`${inputClasses} m3-field__textarea`}
            rows={rows}
            required={required}
            aria-invalid={Boolean(error)}
            aria-describedby={description}
            {...(props as unknown as TextareaHTMLAttributes<HTMLTextAreaElement>)}
          />
        ) : (
          <input
            id={fieldId}
            className={inputClasses}
            required={required}
            aria-invalid={Boolean(error)}
            aria-describedby={description}
            {...props}
          />
        )}
        {suffix ? <span className="m3-field__suffix">{suffix}</span> : null}
        {trailing ? (
          <span className="m3-field__trailing">{trailing}</span>
        ) : null}
      </div>
      {error ? (
        <p
          className="m3-field__message m3-field__message--error"
          id={messageId}
          role="alert"
        >
          {error}
        </p>
      ) : helper ? (
        <p className="m3-field__message" id={messageId}>
          {helper}
        </p>
      ) : null}
    </div>
  )
}

export type SelectOption = { value: string; label: string }

type M3SelectItem = {
  id: string
  label: string
}

const EMPTY_OPTION_KEY = "__m3_empty_option__"

function selectItems(options: SelectOption[]): M3SelectItem[] {
  return options.map((option) => ({
    id: option.value === "" ? EMPTY_OPTION_KEY : option.value,
    label: option.label,
  }))
}

function valueToKey(value: string, options: SelectOption[]): string | null {
  if (value === "") {
    return options.some((option) => option.value === "")
      ? EMPTY_OPTION_KEY
      : null
  }
  return value
}

function keyToValue(key: string | number | null): string {
  if (key === null || key === EMPTY_OPTION_KEY) return ""
  return String(key)
}

function FieldSupport({ error, helper }: { error?: string; helper?: string }) {
  return (
    <>
      <FieldError className="m3-field__message m3-field__message--error">
        {error}
      </FieldError>
      {!error && helper ? (
        <AriaText slot="description" className="m3-field__message">
          {helper}
        </AriaText>
      ) : null}
    </>
  )
}

function listBoxItem(item: M3SelectItem) {
  return (
    <ListBoxItem
      id={item.id}
      textValue={item.label}
      className="m3-listbox__item"
    >
      {({ isSelected }) => (
        <>
          <span className="m3-listbox__indicator" aria-hidden>
            {isSelected ? <Check size={18} /> : null}
          </span>
          <span className="m3-listbox__label">{item.label}</span>
        </>
      )}
    </ListBoxItem>
  )
}

function EmptyListBoxState({ emptyLabel }: { emptyLabel: string }) {
  return <div className="m3-listbox__empty">{emptyLabel}</div>
}

function SelectListBox({
  items,
  emptyLabel,
}: {
  items: M3SelectItem[]
  emptyLabel: string
}) {
  return (
    <ListBox
      items={items}
      className="m3-listbox"
      renderEmptyState={() => <EmptyListBoxState emptyLabel={emptyLabel} />}
    >
      {listBoxItem}
    </ListBox>
  )
}

function ComboBoxListBox({ emptyLabel }: { emptyLabel: string }) {
  return (
    <ListBox
      className="m3-listbox"
      renderEmptyState={() => <EmptyListBoxState emptyLabel={emptyLabel} />}
    >
      {listBoxItem}
    </ListBox>
  )
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  error,
  helper,
  required,
  placeholder,
  id,
  disabled,
  containerClassName = "",
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  error?: string
  helper?: string
  required?: boolean
  placeholder?: string
  id?: string
  disabled?: boolean
  containerClassName?: string
}) {
  const { t, direction, locale } = useI18n()
  const isMobile = useMobileViewport()
  const localeTag =
    locale === "fa" ? "fa-IR-u-ca-persian" : "en-US-u-ca-gregory"
  const items = selectItems(options)
  const selectedKey = valueToKey(value, options)
  return (
    <I18nProvider locale={localeTag}>
      <AriaSelect
        id={id}
        value={selectedKey}
        onChange={(key) => onChange(keyToValue(key))}
        isDisabled={disabled}
        isInvalid={Boolean(error)}
        isRequired={required}
        placeholder={placeholder ?? t("common.choose")}
        dir={direction}
        className={`m3-field m3-picker-field m3-select ${error ? "is-invalid" : ""} ${containerClassName}`}
      >
        <AriaLabel className="m3-field__label">
          {label}
          {required ? (
            <span className="m3-field__required" aria-hidden>
              *
            </span>
          ) : null}
        </AriaLabel>
        <AriaButton className="m3-field__control m3-select__button">
          <SelectValue className="m3-select__value" />
          <ChevronDown className="m3-select__chevron" size={20} aria-hidden />
        </AriaButton>
        <FieldSupport error={error} helper={helper} />
        <AriaPopover
          className="m3-select-popover"
          offset={6}
          containerPadding={12}
          placement={isMobile ? "top start" : "bottom start"}
          dir={direction}
        >
          <SelectListBox items={items} emptyLabel={t("common.noResults")} />
        </AriaPopover>
      </AriaSelect>
    </I18nProvider>
  )
}

export function SearchableSelectField({
  label,
  value,
  onChange,
  options,
  error,
  helper,
  required,
  placeholder,
  id,
  disabled,
  containerClassName = "",
  inputValue,
  onInputChange,
  defaultFilter,
  emptyLabel,
  footer,
  footerRef,
  loading = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  error?: string
  helper?: string
  required?: boolean
  placeholder?: string
  id?: string
  disabled?: boolean
  containerClassName?: string
  inputValue?: string
  onInputChange?: (value: string) => void
  defaultFilter?: (textValue: string, inputValue: string) => boolean
  emptyLabel?: string
  footer?: ReactNode
  footerRef?: RefObject<HTMLDivElement | null>
  loading?: boolean
}) {
  const { t, direction, locale } = useI18n()
  const isMobile = useMobileViewport()
  const localeTag =
    locale === "fa" ? "fa-IR-u-ca-persian" : "en-US-u-ca-gregory"
  const items = selectItems(options)
  const selectedKey = valueToKey(value, options)
  return (
    <I18nProvider locale={localeTag}>
      <AriaComboBox
        id={id}
        value={selectedKey}
        onChange={(key) => onChange(keyToValue(key))}
        defaultItems={items}
        inputValue={inputValue}
        onInputChange={onInputChange}
        defaultFilter={defaultFilter}
        isDisabled={disabled}
        isInvalid={Boolean(error)}
        isRequired={required}
        allowsEmptyCollection
        menuTrigger="focus"
        dir={direction}
        aria-busy={loading}
        className={`m3-field m3-picker-field m3-combobox ${error ? "is-invalid" : ""} ${containerClassName}`}
      >
        <AriaLabel className="m3-field__label">
          {label}
          {required ? (
            <span className="m3-field__required" aria-hidden>
              *
            </span>
          ) : null}
        </AriaLabel>
        <Group className="m3-field__control m3-combobox__control">
          <Search size={18} className="m3-combobox__search" aria-hidden />
          <AriaInput
            className="m3-combobox__input"
            placeholder={placeholder ?? t("common.choose")}
          />
          <AriaButton
            className="m3-combobox__trigger"
            aria-label={t("common.showOptions")}
          >
            <ChevronDown size={20} aria-hidden />
          </AriaButton>
        </Group>
        <FieldSupport error={error} helper={helper} />
        <AriaPopover
          className="m3-select-popover m3-combobox__popover"
          offset={6}
          containerPadding={12}
          placement={isMobile ? "top start" : "bottom start"}
          dir={direction}
          shouldCloseOnInteractOutside={(element) =>
            !footerRef?.current?.contains(element as Node)
          }
        >
          <ComboBoxListBox emptyLabel={emptyLabel ?? t("common.noResults")} />
          {footer}
        </AriaPopover>
      </AriaComboBox>
    </I18nProvider>
  )
}

export function Switch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <label className="m3-switch">
      <span>{label}</span>
      <button
        type="button"
        role="switch"
        aria-label={label}
        aria-checked={checked}
        className="m3-switch__track"
        data-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span className="m3-switch__thumb" />
      </button>
    </label>
  )
}

export function Chip({
  children,
  selected,
  onClick,
  icon,
}: {
  children: ReactNode
  selected?: boolean
  onClick?: () => void
  icon?: ReactNode
}) {
  return (
    <button
      type="button"
      className={`m3-chip ${selected ? "m3-chip--selected" : ""}`}
      onClick={onClick}
      aria-pressed={selected}
    >
      {icon}
      {children}
    </button>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n()
  const key = `status.${status.toLowerCase()}` as
    | "status.draft"
    | "status.active"
    | "status.archived"
    | "status.inactive"
  const label = [
    "status.draft",
    "status.active",
    "status.archived",
    "status.inactive",
  ].includes(key)
    ? t(key)
    : status
  return (
    <span className={`m3-status m3-status--${status.toLowerCase()}`}>
      {label}
    </span>
  )
}

export function Tabs({
  tabs,
  value,
  onChange,
  idPrefix = "m3-tabs",
}: {
  tabs: { value: string; label: string; count?: number }[]
  value: string
  onChange: (value: string) => void
  idPrefix?: string
}) {
  const { formatNumber, direction } = useI18n()
  return (
    <div
      className="m3-tabs"
      role="tablist"
      onKeyDown={(event) => {
        const keys = ["ArrowLeft", "ArrowRight", "Home", "End"]
        if (!keys.includes(event.key)) return
        const buttons = Array.from(
          event.currentTarget.querySelectorAll<HTMLButtonElement>(
            '[role="tab"]',
          ),
        )
        const current = buttons.indexOf(
          document.activeElement as HTMLButtonElement,
        )
        let next = current
        if (event.key === "Home") next = 0
        else if (event.key === "End") next = buttons.length - 1
        else if (event.key === "ArrowLeft") {
          next = direction === "rtl" ? current + 1 : current - 1
        } else {
          next = direction === "rtl" ? current - 1 : current + 1
        }
        if (next < 0 || next >= buttons.length) return
        event.preventDefault()
        buttons[next].focus()
        onChange(tabs[next].value)
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          id={`${idPrefix}-tab-${tab.value}`}
          role="tab"
          aria-selected={value === tab.value}
          aria-controls={`${idPrefix}-panel-${tab.value}`}
          tabIndex={value === tab.value ? 0 : -1}
          className={`m3-tabs__tab ${value === tab.value ? "is-active" : ""}`}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
          {tab.count !== undefined ? (
            <span className="m3-tabs__count">{formatNumber(tab.count)}</span>
          ) : null}
        </button>
      ))}
    </div>
  )
}

export function Dialog({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  size = "md",
  dismissible = true,
}: {
  open: boolean
  title: string
  description?: string
  children?: ReactNode
  footer?: ReactNode
  onClose: () => void
  size?: "sm" | "md" | "lg"
  dismissible?: boolean
}) {
  const { t } = useI18n()
  const dialogRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  const dismissibleRef = useRef(dismissible)
  onCloseRef.current = onClose
  dismissibleRef.current = dismissible
  useEffect(() => {
    if (!open) return
    const previousFocus = document.activeElement as HTMLElement | null
    const focusable = () =>
      Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]",
        ) ?? [],
      )
    const frame = window.requestAnimationFrame(() => {
      const firstField = dialogRef.current?.querySelector<HTMLElement>(
        "input:not([disabled]), textarea:not([disabled]), select:not([disabled])",
      )
      ;(firstField ?? focusable()[0])?.focus()
    })
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        const openPopover = document.querySelector(
          ".m3-select-popover, .m3-date-popover, .m3-calendar__picker-popover",
        )
        if (openPopover?.getClientRects().length) return
        if (dismissibleRef.current) onCloseRef.current()
      }
      if (event.key !== "Tab") return
      const items = focusable()
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener("keydown", onKey, true)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      window.cancelAnimationFrame(frame)
      document.removeEventListener("keydown", onKey, true)
      document.body.style.overflow = previousOverflow
      previousFocus?.focus()
    }
  }, [open])

  if (!open) return null
  return createPortal(
    <div className="m3-scrim">
      <div
        ref={dialogRef}
        className={`m3-dialog m3-dialog--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="m3-dialog-title"
      >
        <header className="m3-dialog__header">
          <div>
            <h2 id="m3-dialog-title">{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          <IconButton
            label={t("common.close")}
            onClick={onClose}
            disabled={!dismissible}
          >
            <X size={20} />
          </IconButton>
        </header>
        {children ? <div className="m3-dialog__content">{children}</div> : null}
        {footer ? (
          <footer className="m3-dialog__footer">{footer}</footer>
        ) : null}
      </div>
    </div>,
    document.body,
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="m3-loading" role="status">
      <span className="m3-spinner" aria-hidden />
      {label ? <span>{label}</span> : null}
    </div>
  )
}

export function LinearProgress() {
  return (
    <div className="m3-linear-progress" role="progressbar">
      <span />
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="m3-empty">
      {icon ? <div className="m3-empty__icon">{icon}</div> : null}
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action ? <div className="m3-empty__action">{action}</div> : null}
    </div>
  )
}

export function ErrorState({
  message,
  onRetry,
  retryLabel,
}: {
  message: string
  onRetry?: () => void
  retryLabel?: string
}) {
  return (
    <div className="m3-error-state" role="alert">
      <p>{message}</p>
      {onRetry ? (
        <Button variant="outlined" onClick={onRetry}>
          {retryLabel}
        </Button>
      ) : null}
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
  onBack,
  backLabel,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
  onBack?: () => void
  backLabel?: string
}) {
  const { direction, t } = useI18n()
  const BackIcon = direction === "rtl" ? ArrowRight : ArrowLeft
  return (
    <header className="m3-page-header">
      <div className="m3-page-header__text">
        {onBack ? (
          <button type="button" className="m3-back-button" onClick={onBack}>
            <BackIcon size={18} aria-hidden />
            <span>{backLabel ?? t("common.back")}</span>
          </button>
        ) : null}
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? (
        <div className="m3-page-header__actions">{actions}</div>
      ) : null}
    </header>
  )
}

export function Avatar({ name }: { name?: string | null }) {
  const initials = (name ?? "?")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0))
    .join("")
  return <span className="m3-avatar">{initials || "?"}</span>
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="m3-filter-bar">{children}</div>
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onClose,
  destructive = false,
  loading = false,
}: {
  open: boolean
  title: string
  description?: string
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onClose: () => void
  destructive?: boolean
  loading?: boolean
}) {
  return (
    <Dialog
      open={open}
      title={title}
      description={description}
      onClose={onClose}
      dismissible={!loading}
      footer={
        <>
          <Button variant="text" onClick={onClose} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? "danger" : "filled"}
            onClick={onConfirm}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </>
      }
    />
  )
}

export function useDisclosure(initial = false) {
  const [open, setOpen] = useState(initial)
  return {
    open,
    onOpen: () => setOpen(true),
    onClose: () => setOpen(false),
    toggle: () => setOpen((value) => !value),
  }
}
