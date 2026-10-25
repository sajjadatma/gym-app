import { createFileRoute, Navigate } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { Spinner } from "@/components/M3"
import { useI18n } from "@/i18n"
import { PrintPage } from "@/pages/PrintPage"

function Page() {
  const { versionId } = Route.useParams()
  const { me, isLoading } = useAuth()
  const { t } = useI18n()
  if (isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (!me) return <Navigate to="/login" replace />
  return <PrintPage versionId={versionId} />
}

export const Route = createFileRoute("/print/$versionId")({
  component: Page,
})
