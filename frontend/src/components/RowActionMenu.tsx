import { MoreHorizontal } from "lucide-react"
import {
  type CSSProperties,
  Fragment,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react"
import { createPortal } from "react-dom"

import { useI18n } from "@/i18n"

export type RowActionItem = {
  key: string
  label: string
  icon?: ReactNode
  onSelect: () => void
  disabled?: boolean
  destructive?: boolean
  separatorBefore?: boolean
}

const MENU_WIDTH = 208

export function RowActionMenu({
  items,
  label,
  disabled,
}: {
  items: RowActionItem[]
  label?: string
  disabled?: boolean
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [style, setStyle] = useState<CSSProperties>({})
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const menuId = useId()
  const accessibleLabel = label ?? t("common.moreActions")

  const close = useCallback(() => setOpen(false), [])

  useLayoutEffect(() => {
    if (!open) return
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const direction = getComputedStyle(document.documentElement).direction
    const desiredLeft =
      direction === "rtl" ? rect.right - MENU_WIDTH : rect.left
    const left = Math.min(
      Math.max(8, desiredLeft),
      Math.max(8, window.innerWidth - MENU_WIDTH - 8),
    )
    const spaceBelow = window.innerHeight - rect.bottom
    const openAbove = spaceBelow < 220 && rect.top > spaceBelow
    setStyle(
      openAbove
        ? {
            left,
            bottom: window.innerHeight - rect.top + 6,
            width: MENU_WIDTH,
          }
        : {
            left,
            top: rect.bottom + 6,
            width: MENU_WIDTH,
          },
    )
    const frame = requestAnimationFrame(() => {
      menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
    })
    return () => cancelAnimationFrame(frame)
  }, [open])

  useEffect(() => {
    if (!open) return
    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node
      if (
        triggerRef.current?.contains(target) ||
        menuRef.current?.contains(target)
      ) {
        return
      }
      close()
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return
      event.preventDefault()
      close()
      triggerRef.current?.focus()
    }
    function handleResize() {
      close()
    }
    function handleScroll(event: Event) {
      if (menuRef.current?.contains(event.target as Node)) return
      close()
    }
    document.addEventListener("pointerdown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    window.addEventListener("resize", handleResize)
    window.addEventListener("scroll", handleScroll, true)
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
      window.removeEventListener("resize", handleResize)
      window.removeEventListener("scroll", handleScroll, true)
    }
  }, [open, close])

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="m3-icon-button m3-row-actions__more"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={accessibleLabel}
        title={accessibleLabel}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
      >
        <MoreHorizontal size={18} aria-hidden />
      </button>
      {open
        ? createPortal(
            <div
              ref={menuRef}
              id={menuId}
              role="menu"
              aria-label={accessibleLabel}
              className="m3-row-menu"
              style={style}
              onKeyDown={(event) => {
                if (event.key === "Tab") {
                  event.preventDefault()
                  close()
                  triggerRef.current?.focus()
                  return
                }
                if (
                  !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)
                ) {
                  return
                }
                const menuItems = Array.from(
                  menuRef.current?.querySelectorAll<HTMLElement>(
                    '[role="menuitem"]:not(:disabled)',
                  ) ?? [],
                )
                if (!menuItems.length) return
                event.preventDefault()
                const current = menuItems.indexOf(
                  document.activeElement as HTMLElement,
                )
                if (event.key === "Home") {
                  menuItems[0].focus()
                } else if (event.key === "End") {
                  menuItems[menuItems.length - 1].focus()
                } else if (event.key === "ArrowDown") {
                  menuItems[(current + 1) % menuItems.length].focus()
                } else {
                  menuItems[
                    (current - 1 + menuItems.length) % menuItems.length
                  ].focus()
                }
              }}
            >
              {items.map((item) => (
                <Fragment key={item.key}>
                  {item.separatorBefore ? (
                    <hr className="m3-row-menu__separator" />
                  ) : null}
                  <button
                    type="button"
                    role="menuitem"
                    className={`m3-row-menu__item ${
                      item.destructive ? "is-danger" : ""
                    }`}
                    disabled={item.disabled}
                    onClick={() => {
                      close()
                      item.onSelect()
                    }}
                  >
                    {item.icon ? (
                      <span className="m3-row-menu__icon" aria-hidden>
                        {item.icon}
                      </span>
                    ) : null}
                    <span>{item.label}</span>
                  </button>
                </Fragment>
              ))}
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
