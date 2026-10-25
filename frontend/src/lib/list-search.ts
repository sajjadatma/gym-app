import { stripSearchParams } from "@tanstack/react-router"

export const PAGE_SIZES = [10, 25, 50] as const
export type PageSize = (typeof PAGE_SIZES)[number]

export type ListTab = "active" | "archived"

export type ListSearch = {
  page?: number
  size?: PageSize
  q?: string
}

export type GlobalListSearch = ListSearch & {
  club?: string
  tab?: ListTab
}

function positiveInt(value: unknown): number | null {
  const number = Number(value)
  return Number.isInteger(number) && number > 0 ? number : null
}

function pageSize(value: unknown): PageSize {
  const number = Number(value)
  return PAGE_SIZES.includes(number as PageSize)
    ? (number as PageSize)
    : PAGE_SIZES[0]
}

function text(value: unknown): string {
  return typeof value === "string" ? value : ""
}

export function parseListSearch(search: Record<string, unknown>): ListSearch {
  return {
    page: positiveInt(search.page) ?? 1,
    size: pageSize(search.size),
    q: text(search.q),
  }
}

export function parseGlobalListSearch(
  search: Record<string, unknown>,
): GlobalListSearch {
  return {
    ...parseListSearch(search),
    club: text(search.club),
    tab: search.tab === "archived" ? "archived" : "active",
  }
}

export const listSearchDefaults = {
  page: 1,
  size: PAGE_SIZES[0],
  q: "",
}

export const globalListSearchDefaults = {
  ...listSearchDefaults,
  club: "",
  tab: "active" as const,
}

export const stripListDefaults =
  stripSearchParams<ListSearch>(listSearchDefaults)
export const stripGlobalListDefaults = stripSearchParams<GlobalListSearch>(
  globalListSearchDefaults,
)

/** Defaults are omitted from the URL so shared links stay readable. */
export function pageParam(page: number): number | undefined {
  return page <= 1 ? undefined : page
}

export function sizeParam(size: PageSize): PageSize | undefined {
  return size === PAGE_SIZES[0] ? undefined : size
}

export function textParam(value: string): string | undefined {
  return value.trim() ? value : undefined
}
