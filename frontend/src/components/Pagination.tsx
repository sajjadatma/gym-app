import { ChevronLeft, ChevronRight } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { useI18n } from "@/i18n"
import { Button, SelectField } from "./M3"

const PAGE_SIZES = [10, 25, 50]

export function usePagination<T>(
  items: T[],
  resetKey?: string,
  initialPageSize = 10,
) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(initialPageSize)
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize))

  // biome-ignore lint/correctness/useExhaustiveDependencies: reset page when filters/tab change
  useEffect(() => {
    setPage(1)
  }, [resetKey])

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount))
  }, [pageCount])

  const start = (page - 1) * pageSize
  const pageItems = useMemo(
    () => items.slice(start, start + pageSize),
    [items, start, pageSize],
  )

  return {
    page,
    pageCount,
    pageSize,
    pageItems,
    start: items.length === 0 ? 0 : start + 1,
    end: Math.min(start + pageSize, items.length),
    total: items.length,
    setPage,
    setPageSize: (size: number) => {
      setPageSize(size)
      setPage(1)
    },
  }
}

type PaginationBarProps = {
  page: number
  pageCount: number
  pageSize: number
  total: number
  start: number
  end: number
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
  onPageChange,
  onPageSizeChange,
}: PaginationBarProps) {
  const { t, formatNumber, direction } = useI18n()
  const PreviousIcon = direction === "rtl" ? ChevronRight : ChevronLeft
  const NextIcon = direction === "rtl" ? ChevronLeft : ChevronRight

  if (total === 0) return null
  if (total <= pageSize && pageSize === 10) return null

  return (
    <nav className="m3-pagination" aria-label={t("common.pagination")}>
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
