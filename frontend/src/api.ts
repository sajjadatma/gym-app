import { AxiosError } from "axios"

import { client } from "./client/client.gen"
import type { TranslationKey } from "./i18n"

const baseURL = import.meta.env.VITE_API_URL ?? ""
const CSRF_COOKIE = "gym_csrf_token"
const SAFE_METHODS = ["get", "head", "options", "trace"]

function cookie(name: string): string | null {
  if (typeof document === "undefined") return null
  const prefix = `${name}=`
  for (const part of document.cookie.split(";")) {
    const value = part.trim()
    if (value.startsWith(prefix)) {
      return decodeURIComponent(value.slice(prefix.length))
    }
  }
  return null
}

client.setConfig({
  baseURL,
  withCredentials: true,
})

client.instance.interceptors.request.use((config) => {
  const gymId = localStorage.getItem("gym.activeGymId")
  if (gymId) config.headers.set("X-Gym-ID", gymId)
  const method = (config.method ?? "get").toLowerCase()
  if (!SAFE_METHODS.includes(method)) {
    const csrf = cookie(CSRF_COOKIE)
    if (csrf) config.headers.set("X-CSRF-Token", csrf)
  }
  return config
})

client.instance.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const detail = getApiErrorDetail(error)
    const url = error.config?.url ?? ""
    const isAuthProbe = url.includes("/users/me")
    if (error.response?.status === 401) {
      if (!isAuthProbe && !window.location.pathname.startsWith("/login")) {
        window.location.assign("/login")
      }
    }
    if (
      error.response?.status === 403 &&
      detail === "password_change_required"
    ) {
      window.dispatchEvent(new CustomEvent("gym:password-required"))
    }
    if (
      error.response?.status === 403 &&
      ["invalid_credentials", "invalid_token"].includes(detail ?? "") &&
      !isAuthProbe
    ) {
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login")
      }
    }
    return Promise.reject(error)
  },
)

export function getApiErrorDetail(error: unknown): string | null {
  if (error instanceof AxiosError) {
    const data = error.response?.data as
      | { detail?: string | Array<{ msg?: string }> }
      | undefined
    if (typeof data?.detail === "string") return data.detail
    if (Array.isArray(data?.detail)) return "validation_error"
  }
  return null
}

export function getApiStatus(error: unknown): number | null {
  return error instanceof AxiosError ? (error.response?.status ?? null) : null
}

export function translateApiError(
  error: unknown,
  t: (key: TranslationKey) => string,
): string {
  const detail = getApiErrorDetail(error)
  if (detail) {
    const key = `errors.${detail}` as TranslationKey
    const translated = t(key)
    if (translated !== key) return translated
  }
  if (error instanceof AxiosError && !error.response) {
    return t("errors.network")
  }
  if (getApiStatus(error) === 422) return t("errors.validation")
  return t("errors.generic")
}

export function isAxiosError(error: unknown): error is AxiosError {
  return error instanceof AxiosError
}
