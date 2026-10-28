import { createFileRoute, Navigate } from "@tanstack/react-router"

import { useAuth } from "@/auth"
import { Spinner } from "@/components/M3"
import { useI18n } from "@/i18n"
import { PrintPage } from "@/pages/PrintPage"

function Page() {
  const { versionId } = Route.useParams()
  const { gym } = Route.useSearch()
  const { me, isLoading } = useAuth()
  const { t } = useI18n()
  if (isLoading) {
    return <Spinner label={t("common.loading")} />
  }
  if (!me) return <Navigate to="/login" replace />
  return <PrintPage versionId={versionId} gymId={gym} />
}

export const Route = createFileRoute("/print/$versionId")({
  validateSearch: (search: Record<string, unknown>): { gym?: string } => ({
    gym: typeof search.gym === "string" ? search.gym : undefined,
  }),
  component: Page,
})
