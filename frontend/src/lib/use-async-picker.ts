import { useInfiniteQuery } from "@tanstack/react-query"
import { useEffect, useRef, useState } from "react"

export type PickerPage<T> = {
  data: T[]
  count: number
}

type Options<T> = {
  queryKey: readonly unknown[]
  enabled: boolean
  fetchPage: (
    search: string,
    offset: number,
    limit: number,
  ) => Promise<PickerPage<T>>
  pageSize?: number
  resetKey?: string
}

const SEARCH_DEBOUNCE_MS = 250

/**
 * Server-searched options for a picker. Only the first page is loaded until
 * the user types or asks for more, so large clubs never require downloading
 * every eligible person.
 */
export function useAsyncPicker<T>({
  queryKey,
  enabled,
  fetchPage,
  pageSize = 20,
  resetKey = "",
}: Options<T>) {
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [activeKey, setActiveKey] = useState(resetKey)
  const fetchRef = useRef(fetchPage)
  fetchRef.current = fetchPage

  if (activeKey !== resetKey) {
    setActiveKey(resetKey)
    setSearch("")
    setDebouncedSearch("")
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim())
    }, SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [search])

  const query = useInfiniteQuery({
    queryKey: [...queryKey, debouncedSearch],
    queryFn: ({ pageParam }) =>
      fetchRef.current(debouncedSearch, pageParam as number, pageSize),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce(
        (total, page) => total + page.data.length,
        0,
      )
      return loaded < lastPage.count ? loaded : undefined
    },
    enabled,
    staleTime: 30_000,
  })

  // A search is still debouncing or in flight. The list may show the previous
  // page for a moment; callers must not commit a selection until it settles.
  const searching = search.trim() !== debouncedSearch
  const items = query.data?.pages.flatMap((page) => page.data) ?? []
  const total = query.data?.pages[0]?.count ?? 0

  return {
    search,
    setSearch,
    searching,
    items,
    total,
    isLoading: searching || query.isLoading,
    isFetching: query.isFetching,
    isLoadingMore: query.isFetchingNextPage,
    hasMore: Boolean(query.hasNextPage),
    error: query.error,
    loadMore: () => query.fetchNextPage(),
    retry: () => query.refetch(),
  }
}

export type AsyncPicker<T> = ReturnType<typeof useAsyncPicker<T>>
