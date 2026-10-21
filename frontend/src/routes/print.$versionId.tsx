import { createFileRoute, redirect } from "@tanstack/react-router"

import { PrintPage } from "@/pages/PrintPage"

function Page() {
  const { versionId } = Route.useParams()
  return <PrintPage versionId={versionId} />
}

export const Route = createFileRoute("/print/$versionId")({
  beforeLoad: () => {
    if (!localStorage.getItem("access_token")) {
      throw redirect({ to: "/login" })
    }
  },
  component: Page,
})
