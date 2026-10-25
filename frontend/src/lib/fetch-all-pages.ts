type PageResponse<T> = {
  data: T[]
  count: number
}

/**
 * Collect every page of a paginated endpoint.
 *
 * Only for selector data sources (for example the athlete picker in the
 * template dialog), where every eligible record must stay reachable. List
 * tables fetch one page at a time.
 */
export async function fetchAllPages<T>(
  fetchPage: (offset: number, limit: number) => Promise<PageResponse<T>>,
  pageSize = 50,
): Promise<T[]> {
  const items: T[] = []
  let offset = 0

  for (;;) {
    const response = await fetchPage(offset, pageSize)
    items.push(...response.data)
    if (items.length >= response.count || response.data.length === 0) {
      return items
    }
    offset += pageSize
  }
}
