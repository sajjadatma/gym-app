import { ChevronLeft, ChevronRight } from "lucide-react"
import { useState } from "react"

import { useI18n } from "@/i18n"
import { Button, SelectField } from "./M3"

export const DEFAULT_PAGE_SIZE = 10
const PAGE_SIZES = [10, 25, 50]

/**
 * Pager state for a server-paginated list. `total` is not needed here: the
 * request offset/limit must be known before the page is fetched.
 */
export function usePager(resetKey = "") {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [activeKey, setActiveKey] = useState(resetKey)

  // Reset during render so the first request after a filter change never asks
  // for the old page number.
  if (activeKey !== resetKey) {
    setActiveKey(resetKey)
    setPage(1)
  }

  return {
    page,
    pageSize,
    offset: (page - 1) * pageSize,
    limit: pageSize,
    setPage,
    setPageSize: (size: number) => {
      setPageSize(size)
      setPage(1)
    },
  }
}

/**
 * Clamp the pager to the server's total and derive the visible range.
 * Callers should pass `page` back to `setPage` when it differs from
 * `pager.page`, so deleting the last row of a page cannot leave an
 * out-of-range request in place.
 */
export function pageWindow(
  pager: Pick<ReturnType<typeof usePager>, "page" | "pageSize">,
  total: number,
) {
  const pageCount = Math.max(1, Math.ceil(total / pager.pageSize))
  const page = Math.min(pager.page, pageCount)
  return {
    page,
    pageCount,
    total,
    start: total === 0 ? 0 : (page - 1) * pager.pageSize + 1,
    end: Math.min(page * pager.pageSize, total),
  }
}

type PaginationBarProps = {
  page: number
  pageCount: number
  pageSize: number
  total: number
  start: number
  end: number
  loading?: boolean
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
}

export function PaginationBar({
  page,
  pageCount,
  pageSize,
  total,
  start,
  end,
  loading = false,
  onPageChange,
  onPageSizeChange,
}: PaginationBarProps) {
  const { t, formatNumber, direction } = useI18n()
  const PreviousIcon = direction === "rtl" ? ChevronRight : ChevronLeft
  const NextIcon = direction === "rtl" ? ChevronLeft : ChevronRight

  if (total === 0) return null
  if (total <= pageSize && pageSize === DEFAULT_PAGE_SIZE) return null

  return (
    <nav
      className="m3-pagination"
      aria-label={t("common.pagination")}
      aria-busy={loading}
    >
      <div className="m3-pagination__size">
        <SelectField
          label={t("common.rowsPerPage")}
          value={String(pageSize)}
          onChange={(value) => onPageSizeChange(Number(value))}
          options={PAGE_SIZES.map((size) => ({
            value: String(size),
            label: formatNumber(size),
          }))}
        />
      </div>
      <span className="m3-pagination__status" aria-live="polite">
        {t("common.pageStatus", {
          start: formatNumber(start),
          end: formatNumber(end),
          total: formatNumber(total),
        })}
      </span>
      <div className="m3-pagination__controls">
        <Button
          variant="outlined"
          size="sm"
          icon={<PreviousIcon size={15} aria-hidden />}
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          {t("common.previous")}
        </Button>
        <span className="m3-pagination__page">
          {t("common.pageOf", {
            page: formatNumber(page),
            pages: formatNumber(pageCount),
          })}
        </span>
        <Button
          variant="outlined"
          size="sm"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          {t("common.next")}
          <NextIcon size={15} aria-hidden />
        </Button>
      </div>
    </nav>
  )
}
