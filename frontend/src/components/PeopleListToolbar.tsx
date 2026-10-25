import { LayoutGrid, Search, Table2, X } from "lucide-react"

import { SelectField, type SelectOption, TextField } from "@/components/M3"

export type PeopleView = "grid" | "table"
export type PeopleTab = "active" | "archived"

type PeopleListToolbarProps = {
  search: string
  onSearch: (value: string) => void
  searchLabel: string
  clearSearchLabel: string
  countLabel: string
  view: PeopleView
  onViewChange: (view: PeopleView) => void
  viewLabel: string
  gridLabel: string
  tableLabel: string
  clubValue: string
  onClubChange: (value: string) => void
  clubLabel: string
  clubOptions: SelectOption[]
  tab: PeopleTab
  onTabChange: (tab: PeopleTab) => void
  tabLabel: string
  activeLabel: string
  archivedLabel: string
}

export function PeopleListToolbar({
  search,
  onSearch,
  searchLabel,
  clearSearchLabel,
  countLabel,
  view,
  onViewChange,
  viewLabel,
  gridLabel,
  tableLabel,
  clubValue,
  onClubChange,
  clubLabel,
  clubOptions,
  tab,
  onTabChange,
  tabLabel,
  activeLabel,
  archivedLabel,
}: PeopleListToolbarProps) {
  return (
    <>
      <nav className="m3-tabs" aria-label={tabLabel}>
        <button
          type="button"
          className={`m3-tabs__tab ${tab === "active" ? "is-active" : ""}`}
          aria-current={tab === "active" ? "page" : undefined}
          onClick={() => onTabChange("active")}
        >
          {activeLabel}
        </button>
        <button
          type="button"
          className={`m3-tabs__tab ${tab === "archived" ? "is-active" : ""}`}
          aria-current={tab === "archived" ? "page" : undefined}
          onClick={() => onTabChange("archived")}
        >
          {archivedLabel}
        </button>
      </nav>

      <section className="m3-list-toolbar">
        <div className="m3-list-toolbar__search">
          <TextField
            label={searchLabel}
            type="search"
            name="search"
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            leading={<Search size={18} aria-hidden />}
            trailing={
              search ? (
                <button
                  type="button"
                  className="m3-search-clear"
                  aria-label={clearSearchLabel}
                  onClick={() => onSearch("")}
                >
                  <X size={15} aria-hidden />
                </button>
              ) : undefined
            }
          />
        </div>
        <div className="m3-list-toolbar__club">
          <SelectField
            label={clubLabel}
            value={clubValue}
            onChange={onClubChange}
            options={clubOptions}
          />
        </div>
        <div className="m3-list-toolbar__actions">
          <span className="m3-count-chip" aria-live="polite">
            {countLabel}
          </span>
          <fieldset className="m3-view-toggle">
            <legend className="sr-only">{viewLabel}</legend>
            <button
              type="button"
              className={`m3-view-toggle__option ${
                view === "grid" ? "is-active" : ""
              }`}
              aria-pressed={view === "grid"}
              aria-label={gridLabel}
              title={gridLabel}
              onClick={() => onViewChange("grid")}
            >
              <LayoutGrid size={16} aria-hidden />
              <span>{gridLabel}</span>
            </button>
            <button
              type="button"
              className={`m3-view-toggle__option ${
                view === "table" ? "is-active" : ""
              }`}
              aria-pressed={view === "table"}
              aria-label={tableLabel}
              title={tableLabel}
              onClick={() => onViewChange("table")}
            >
              <Table2 size={16} aria-hidden />
              <span>{tableLabel}</span>
            </button>
          </fieldset>
        </div>
      </section>
    </>
  )
}
