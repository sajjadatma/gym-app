import { ChevronDown, X } from "lucide-react"
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
  useEffect,
  useId,
  useRef,
  useState,
} from "react"
import { createPortal } from "react-dom"

import { useI18n } from "../i18n"

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
}: {
  children: ReactNode
  className?: string
  variant?: "filled" | "outlined" | "plain"
}) {
  return (
    <section className={`m3-card m3-card--${variant} ${className}`}>
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
  containerClassName = "",
  className = "",
  id,
  required,
  ...props
}: TextFieldProps) {
  const generatedId = useId()
  const fieldId = id ?? generatedId
  const messageId = `${fieldId}-message`
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
            aria-describedby={error || helper ? messageId : undefined}
            {...(props as unknown as TextareaHTMLAttributes<HTMLTextAreaElement>)}
          />
        ) : (
          <input
            id={fieldId}
            className={inputClasses}
            required={required}
            aria-invalid={Boolean(error)}
            aria-describedby={error || helper ? messageId : undefined}
            {...props}
          />
        )}
        {suffix ? <span className="m3-field__suffix">{suffix}</span> : null}
      </div>
      {error ? (
        <p
          className="m3-field__message m3-field__message--error"
          id={messageId}
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
  const generatedId = useId()
  const fieldId = id ?? generatedId
  const messageId = `${fieldId}-message`
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
      <div className="m3-field__control m3-field__control--select">
        <select
          id={fieldId}
          className="m3-field__input m3-field__select"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required={required}
          disabled={disabled}
          aria-invalid={Boolean(error)}
          aria-describedby={error || helper ? messageId : undefined}
        >
          {placeholder ? <option value="">{placeholder}</option> : null}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <ChevronDown size={18} className="m3-field__chevron" aria-hidden />
      </div>
      {error ? (
        <p
          className="m3-field__message m3-field__message--error"
          id={messageId}
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
}: {
  tabs: { value: string; label: string; count?: number }[]
  value: string
  onChange: (value: string) => void
}) {
  const { formatNumber } = useI18n()
  return (
    <div className="m3-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={value === tab.value}
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
}: {
  open: boolean
  title: string
  description?: string
  children?: ReactNode
  footer?: ReactNode
  onClose: () => void
  size?: "sm" | "md" | "lg"
}) {
  const { t } = useI18n()
  const dialogRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
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
      if (event.key === "Escape") onCloseRef.current()
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
    document.addEventListener("keydown", onKey)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      window.cancelAnimationFrame(frame)
      document.removeEventListener("keydown", onKey)
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
          <IconButton label={t("common.close")} onClick={onClose}>
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
  return (
    <header className="m3-page-header">
      <div className="m3-page-header__text">
        {onBack ? (
          <button type="button" className="m3-text-back" onClick={onBack}>
            {backLabel ?? "←"}
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
