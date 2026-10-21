import { CheckCircle2, Info, X, XCircle } from "lucide-react"
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react"
import { useI18n } from "./i18n"

type SnackbarKind = "info" | "success" | "error"

type SnackbarState = {
  id: number
  message: string
  kind: SnackbarKind
}

type SnackbarContextValue = {
  show: (message: string, kind?: SnackbarKind) => void
}

const SnackbarContext = createContext<SnackbarContextValue | null>(null)

export function SnackbarProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const [snackbar, setSnackbar] = useState<SnackbarState | null>(null)
  const timer = useRef<number | null>(null)
  const nextId = useRef(1)

  const show = useCallback((message: string, kind: SnackbarKind = "info") => {
    if (timer.current) window.clearTimeout(timer.current)
    setSnackbar({ id: nextId.current++, message, kind })
    timer.current = window.setTimeout(() => setSnackbar(null), 5200)
  }, [])

  const value = useMemo(() => ({ show }), [show])

  const Icon =
    snackbar?.kind === "success"
      ? CheckCircle2
      : snackbar?.kind === "error"
        ? XCircle
        : Info

  return (
    <SnackbarContext.Provider value={value}>
      {children}
      {snackbar ? (
        <div
          className={`m3-snackbar m3-snackbar--${snackbar.kind}`}
          role="status"
        >
          <Icon size={20} aria-hidden />
          <span>{snackbar.message}</span>
          <button
            type="button"
            className="m3-snackbar__close"
            onClick={() => setSnackbar(null)}
            aria-label={t("common.close")}
          >
            <X size={18} />
          </button>
        </div>
      ) : null}
    </SnackbarContext.Provider>
  )
}

export function useSnackbar() {
  const context = useContext(SnackbarContext)
  if (!context)
    throw new Error("useSnackbar must be used inside SnackbarProvider")
  return context
}
