import { useQuery, useQueryClient } from "@tanstack/react-query"
import { PackagePlus, Plus, Trash2 } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type FinanceCatalogItemPublic, FinanceService } from "@/client"
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorState,
  SectionCard,
  SelectField,
  Spinner,
  Switch,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"
import {
  amountInput,
  type FinanceLineKind,
  type FinanceSectionProps,
  lineKindLabel,
  useMoney,
} from "./shared"

const KINDS: FinanceLineKind[] = [
  "MEMBERSHIP",
  "PROGRAM",
  "SESSION",
  "PACK",
  "PRODUCT",
  "SERVICE",
  "CUSTOM",
]

export function FinanceCatalogSection({ settings, unit }: FinanceSectionProps) {
  const { t, normalizeDigits } = useI18n()
  const { activeGymId } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const { money, parse } = useMoney(unit)
  const canManage = settings.permissions.includes("finance.catalog.manage")

  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<FinanceCatalogItemPublic | null>(null)
  const [name, setName] = useState("")
  const [kind, setKind] = useState<FinanceLineKind>("CUSTOM")
  const [price, setPrice] = useState("")
  const [active, setActive] = useState(true)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const scope = activeGymId ?? ""
  const catalogQuery = useQuery({
    queryKey: ["finance", scope, "catalog", "all"],
    queryFn: async () => (await FinanceService.readFinanceCatalog()).data,
    enabled: Boolean(activeGymId),
  })

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["finance", scope] })
  }

  function openCreate() {
    setEditing(null)
    setName("")
    setKind("CUSTOM")
    setPrice("")
    setActive(true)
    setFormError(null)
    setOpen(true)
  }

  function openEdit(item: FinanceCatalogItemPublic) {
    setEditing(item)
    setName(item.name)
    setKind(item.kind)
    setPrice(
      item.default_price_irr ? amountInput(item.default_price_irr, unit) : "",
    )
    setActive(item.is_active)
    setFormError(null)
    setOpen(true)
  }

  async function save() {
    if (!name.trim()) return
    const priceIrr = price ? parse(price) : 0
    if (priceIrr === null) {
      setFormError(t("finance.invalidAmount"))
      return
    }
    setSaving(true)
    setFormError(null)
    try {
      if (editing) {
        await FinanceService.updateFinanceCatalogItem({
          path: { item_id: editing.id },
          body: {
            name: name.trim(),
            kind,
            default_price_irr: priceIrr,
            is_active: active,
          },
        })
      } else {
        await FinanceService.createFinanceCatalogItem({
          body: { name: name.trim(), kind, default_price_irr: priceIrr },
        })
      }
      await invalidate()
      setOpen(false)
      show(t("finance.catalog.created"), "success")
    } catch (err) {
      setFormError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  const items = catalogQuery.data?.data ?? []

  return (
    <>
      <SectionCard
        title={t("finance.catalog.title")}
        subtitle={t("finance.catalog.subtitle")}
        actions={
          canManage ? (
            <Button icon={<Plus size={16} />} onClick={openCreate}>
              {t("finance.catalog.new")}
            </Button>
          ) : null
        }
      >
        {catalogQuery.isLoading ? (
          <Spinner label={t("common.loading")} />
        ) : catalogQuery.isError ? (
          <ErrorState
            message={translateApiError(catalogQuery.error, t)}
            retryLabel={t("common.retry")}
            onRetry={() => catalogQuery.refetch()}
          />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<PackagePlus size={24} />}
            title={t("finance.catalog.empty")}
          />
        ) : (
          <div className="stack">
            {items.map((item) => (
              <Card key={item.id} variant="outlined">
                <div className="row row--between">
                  <div>
                    <strong>{item.name}</strong>
                    <div className="m3-entity-card__meta">
                      <span>{lineKindLabel(t, item.kind)}</span>
                      <span>{money(item.default_price_irr)}</span>
                      <span className="m3-chip">
                        {item.is_active
                          ? t("finance.catalog.active")
                          : t("finance.catalog.inactive")}
                      </span>
                    </div>
                  </div>
                  {canManage ? (
                    <div className="row" style={{ gap: 8 }}>
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() => openEdit(item)}
                      >
                        {t("common.edit")}
                      </Button>
                      <Button
                        variant="text"
                        size="sm"
                        icon={<Trash2 size={15} />}
                        aria-label={t("finance.catalog.archive")}
                        onClick={() =>
                          void FinanceService.updateFinanceCatalogItem({
                            path: { item_id: item.id },
                            body: { is_active: false },
                          }).then(invalidate)
                        }
                      />
                    </div>
                  ) : null}
                </div>
              </Card>
            ))}
          </div>
        )}
      </SectionCard>

      <Dialog
        open={open}
        title={editing ? t("common.edit") : t("finance.catalog.new")}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button loading={saving} onClick={() => void save()}>
              {t("finance.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {formError ? (
            <div className="m3-inline-alert" role="alert">
              {formError}
            </div>
          ) : null}
          <TextField
            label={t("finance.catalog.name")}
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <SelectField
            label={t("finance.invoice.kind")}
            value={kind}
            onChange={(value) => setKind(value as FinanceLineKind)}
            options={KINDS.map((entry) => ({
              value: entry,
              label: lineKindLabel(t, entry),
            }))}
          />
          <TextField
            label={t("finance.catalog.price")}
            value={price}
            inputMode="decimal"
            dir="auto"
            onChange={(event) => setPrice(normalizeDigits(event.target.value))}
          />
          {editing ? (
            <Switch
              label={t("finance.catalog.active")}
              checked={active}
              onChange={setActive}
            />
          ) : null}
        </div>
      </Dialog>
    </>
  )
}
