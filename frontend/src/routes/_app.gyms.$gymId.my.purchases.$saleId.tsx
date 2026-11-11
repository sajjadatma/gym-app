import { createFileRoute } from "@tanstack/react-router"
import { PurchaseDocumentPage } from "@/pages/PurchaseDocumentPage"
export const Route = createFileRoute("/_app/gyms/$gymId/my/purchases/$saleId")({
  component: () => {
    const { gymId, saleId } = Route.useParams()
    return <PurchaseDocumentPage gymId={gymId} saleId={saleId} />
  },
})
