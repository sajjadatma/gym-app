import { Navigate } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { useI18n } from "@/i18n"
import { Spinner } from "./M3"

type ClubRedirectProps = {
  to: string
  params?: Record<string, string>
}

/**
 * Send legacy root-level club URLs to the same page inside the active club's
 * route space. Club context comes from the URL, so old links only work while a
 * club is active; otherwise the user lands on the clubs list.
 */
export function ClubRedirect({ to, params }: ClubRedirectProps) {
  const { t } = useI18n()
  const { activeGymId, isLoading } = useAuth()

  if (isLoading) return <Spinner label={t("common.loading")} />
  if (!activeGymId) return <Navigate to="/gyms" />

  return (
    <Navigate
      to={to as never}
      params={{ ...params, gymId: activeGymId } as never}
      replace
    />
  )
}
