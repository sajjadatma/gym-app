import { WifiOff } from "lucide-react"
import { useEffect, useState } from "react"

import { useI18n } from "@/i18n"
import { Button } from "./M3"

export function useOnlineStatus() {
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  )

  useEffect(() => {
    const handleOnline = () => setOnline(true)
    const handleOffline = () => setOnline(false)
    window.addEventListener("online", handleOnline)
    window.addEventListener("offline", handleOffline)
    return () => {
      window.removeEventListener("online", handleOnline)
      window.removeEventListener("offline", handleOffline)
    }
  }, [])

  return online
}

export function OfflineBanner() {
  const { t } = useI18n()
  const online = useOnlineStatus()
  if (online) return null
  return (
    <div className="m3-offline-banner" role="status">
      <WifiOff size={15} aria-hidden />
      <span>{t("common.offline")}</span>
    </div>
  )
}

export function OfflineState({ onRetry }: { onRetry: () => void }) {
  const { t } = useI18n()
  return (
    <div className="m3-offline-state">
      <div className="m3-offline-state__card">
        <span className="m3-offline-state__icon" aria-hidden>
          <WifiOff size={26} />
        </span>
        <h1>{t("common.offlineTitle")}</h1>
        <p className="muted">{t("common.offlineHint")}</p>
        <Button icon={<WifiOff size={16} />} onClick={onRetry}>
          {t("common.retry")}
        </Button>
      </div>
    </div>
  )
}
