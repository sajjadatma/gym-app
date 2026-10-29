import "@fontsource-variable/vazirmatn"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"

import "./api"
import "./index.css"
import "./motion.css"
import { AuthProvider } from "./auth"
import { I18nProvider } from "./i18n"
import { routeTree } from "./routeTree.gen"
import { SnackbarProvider } from "./snackbar"
import { ThemeProvider } from "./theme"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 15_000,
    },
  },
})

const router = createRouter({ routeTree })

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker
      .register("/sw.js", { updateViaCache: "none" })
      .then((registration) => registration.update())
      .catch(() => undefined)
  })
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <SnackbarProvider>
            <AuthProvider>
              <RouterProvider router={router} />
            </AuthProvider>
          </SnackbarProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </I18nProvider>
  </StrictMode>,
)
