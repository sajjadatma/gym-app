import { createFileRoute } from "@tanstack/react-router"

import { MyProgramPage } from "@/pages/MyProgramPage"

export const Route = createFileRoute("/_app/my/")({
  component: MyProgramPage,
})
