import { useEffect, useRef, useState } from "react"

import { pageWindow } from "@/components/Pagination"

type Options = {
  page: number
  pageSize: number
  total: number
  /** True only when the response belongs to the page currently requested. */
  isCurrent: boolean
  onPageChange: (page: number, replace?: boolean) => void
}

/**
 * Keeps the visible range aligned with the rows actually rendered, not the
 * page that is still loading. Stale rows must not be acted on until
 * `isCurrent` becomes true.
 */
export function useServerPage({
  page,
  pageSize,
  total,
  isCurrent,
  onPageChange,
}: Options) {
  const [settled, setSettled] = useState({ page, pageSize, total })
  const changeRef = useRef(onPageChange)
  changeRef.current = onPageChange

  if (
    isCurrent &&
    (settled.page !== page ||
      settled.pageSize !== pageSize ||
      settled.total !== total)
  ) {
    setSettled({ page, pageSize, total })
  }

  const window = pageWindow(
    { page: settled.page, pageSize: settled.pageSize },
    settled.total,
  )

  useEffect(() => {
    if (!isCurrent) return
    const current = pageWindow({ page, pageSize }, total)
    if (page > current.pageCount) {
      changeRef.current(current.pageCount, true)
    }
  }, [isCurrent, page, pageSize, total])

  return { window, stale: !isCurrent }
}
