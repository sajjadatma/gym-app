import { useEffect, useRef, useState } from "react"

import { useI18n } from "@/i18n"
import type { AsyncPicker } from "@/lib/use-async-picker"
import { Button, SearchableSelectField, type SelectOption } from "./M3"

type Props<T> = {
  label: string
  value: string
  onChange: (value: string, label: string) => void
  picker: AsyncPicker<T>
  getOption: (item: T) => SelectOption
  filterOption?: (item: T) => boolean
  selectedLabel?: string
  placeholder?: string
  required?: boolean
  error?: string
  helper?: string
}

export function AsyncPickerField<T>({
  label,
  value,
  onChange,
  picker,
  getOption,
  filterOption,
  selectedLabel: initialLabel = "",
  placeholder,
  required,
  error,
  helper,
}: Props<T>) {
  const { t } = useI18n()
  const [selectedLabel, setSelectedLabel] = useState(initialLabel)
  const footerRef = useRef<HTMLDivElement>(null)
  const setSearch = picker.setSearch
  const options = picker.items
    .filter(filterOption ?? (() => true))
    .map(getOption)

  if (value && !options.some((option) => option.value === value)) {
    options.unshift({ value, label: selectedLabel || value })
  }

  useEffect(() => {
    if (value) return
    setSelectedLabel("")
    setSearch("")
  }, [value, setSearch])

  function handleLoadMore() {
    void picker.loadMore()
  }

  function handleChange(next: string) {
    if (picker.searching) return
    const option = options.find((item) => item.value === next)
    const nextLabel = option?.label ?? ""
    setSelectedLabel(nextLabel)
    setSearch(nextLabel)
    onChange(next, nextLabel)
  }

  const footer =
    picker.error ||
    picker.hasMore ||
    picker.isLoadingMore ||
    picker.items.length > 0 ? (
      <div ref={footerRef} className="m3-async-picker__footer">
        {picker.error ? (
          <Button variant="text" size="sm" onClick={picker.retry}>
            {t("common.retry")}
          </Button>
        ) : (
          <Button
            variant="text"
            size="sm"
            onClick={() => {
              if (picker.hasMore) handleLoadMore()
            }}
          >
            {picker.isLoadingMore
              ? t("common.loading")
              : picker.hasMore
                ? t("common.loadMore")
                : t("common.allLoaded")}
          </Button>
        )}
      </div>
    ) : undefined

  return (
    <SearchableSelectField
      label={label}
      value={value}
      onChange={handleChange}
      options={options}
      placeholder={placeholder}
      required={required}
      error={error}
      helper={helper}
      inputValue={picker.search}
      onInputChange={setSearch}
      defaultFilter={() => true}
      emptyLabel={
        picker.isLoading ? t("common.loading") : t("common.noResults")
      }
      footer={footer}
      footerRef={footerRef}
      loading={picker.isFetching}
    />
  )
}
