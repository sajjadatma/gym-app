import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Percent, Plus } from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  SectionCard,
  SelectField,
  Spinner,
  Switch,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import {
  createTax,
  listTaxes,
  type TaxCalculation,
  type TaxDefinition,
  updateTax,
} from "@/lib/finance-api"
import { percentFromBp, tomanToIrr } from "@/lib/finance-ui"
import { useSnackbar } from "@/snackbar"

export function FinanceTaxesPage() {
  const { t, formatNumber } = useI18n()
  const { isSuperuser } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<TaxDefinition | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({
    name: "",
    calculation: "PERCENT" as TaxCalculation,
    percent: "10",
    fixedToman: "50000",
    isActive: true,
    isDefaultVat: false,
  })
  const taxes = useQuery({
    queryKey: ["finance-taxes", isSuperuser],
    queryFn: () => listTaxes(isSuperuser),
  })

  function openCreate() {
    setEditing(null)
    setForm({
      name: "",
      calculation: "PERCENT",
      percent: "10",
      fixedToman: "50000",
      isActive: true,
      isDefaultVat: false,
    })
    setError(null)
    setOpen(true)
  }

  function openEdit(tax: TaxDefinition) {
    setEditing(tax)
    setForm({
      name: tax.name,
      calculation: tax.calculation,
      percent: tax.percent_bp ? percentFromBp(tax.percent_bp) : "10",
      fixedToman: tax.fixed_amount_irr
        ? String(tax.fixed_amount_irr / 10)
        : "50000",
      isActive: tax.is_active,
      isDefaultVat: tax.is_default_vat,
    })
    setError(null)
    setOpen(true)
  }

  async function submit() {
    setSaving(true)
    setError(null)
    const body = {
      name: form.name.trim(),
      calculation: form.calculation,
      percent_bp:
        form.calculation === "PERCENT"
          ? Math.round(Number(form.percent) * 100)
          : null,
      fixed_amount_irr:
        form.calculation === "FIXED"
          ? tomanToIrr(Number(form.fixedToman))
          : null,
      is_active: form.isActive,
      is_default_vat: form.isDefaultVat,
    }
    try {
      if (editing) {
        await updateTax(editing.id, body)
      } else {
        await createTax(body)
      }
      await queryClient.invalidateQueries({ queryKey: ["finance-taxes"] })
      show(t("common.success"), "success")
      setOpen(false)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  if (taxes.isLoading) return <Spinner label={t("common.loading")} />
  if (taxes.isError) {
    return (
      <ErrorState
        message={translateApiError(taxes.error, t)}
        onRetry={() => void taxes.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  return (
    <div className="m3-finance-page">
      <PageHeader
        title={t("finance.taxes.title")}
        subtitle={
          isSuperuser
            ? t("finance.taxes.adminSubtitle")
            : t("finance.taxes.gymSubtitle")
        }
        actions={
          isSuperuser ? (
            <Button icon={<Plus size={17} />} onClick={openCreate}>
              {t("finance.taxes.new")}
            </Button>
          ) : undefined
        }
      />
      <div className="m3-finance-note">
        <Percent size={18} aria-hidden />
        <span>
          {isSuperuser
            ? t("finance.taxes.adminNote")
            : t("finance.taxes.gymNote")}
        </span>
      </div>
      {taxes.data?.length === 0 ? (
        <EmptyState
          icon={<Percent size={24} />}
          title={t("finance.taxes.empty")}
          description={t("finance.taxes.emptyHint")}
        />
      ) : (
        <SectionCard title={t("finance.taxes.listTitle")}>
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("finance.table.name")}</th>
                  <th>{t("finance.table.calculation")}</th>
                  <th>{t("finance.table.value")}</th>
                  <th>{t("finance.table.status")}</th>
                  <th>{t("finance.table.defaultVat")}</th>
                  {isSuperuser ? <th>{t("common.actions")}</th> : null}
                </tr>
              </thead>
              <tbody>
                {taxes.data?.map((tax) => (
                  <tr key={tax.id}>
                    <td>{tax.name}</td>
                    <td>
                      {tax.calculation === "PERCENT"
                        ? t("finance.taxes.percentType")
                        : t("finance.taxes.fixedType")}
                    </td>
                    <td>
                      {tax.calculation === "PERCENT"
                        ? `${percentFromBp(tax.percent_bp ?? 0)}٪`
                        : `${formatNumber((tax.fixed_amount_irr ?? 0) / 10)} ${t("finance.unit.toman")}`}
                    </td>
                    <td>
                      <span
                        className={`m3-status ${tax.is_active ? "m3-status--active" : "m3-status--inactive"}`}
                      >
                        {tax.is_active
                          ? t("finance.taxes.active")
                          : t("finance.taxes.inactive")}
                      </span>
                    </td>
                    <td>
                      {tax.is_default_vat ? t("common.yes") : t("common.no")}
                    </td>
                    {isSuperuser ? (
                      <td>
                        <Button
                          size="sm"
                          variant="text"
                          onClick={() => openEdit(tax)}
                        >
                          {t("common.edit")}
                        </Button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <Dialog
        open={open}
        title={
          editing ? t("finance.taxes.editTitle") : t("finance.taxes.newTitle")
        }
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button
              variant="text"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={() => void submit()} loading={saving}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="m3-form-grid">
          <TextField
            label={t("finance.table.name")}
            value={form.name}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, name: event.target.value }))
            }
            required
          />
          <SelectField
            label={t("finance.table.calculation")}
            value={form.calculation}
            onChange={(value) =>
              setForm((prev) => ({
                ...prev,
                calculation: value as TaxCalculation,
              }))
            }
            options={[
              { value: "PERCENT", label: t("finance.taxes.percentType") },
              { value: "FIXED", label: t("finance.taxes.fixedType") },
            ]}
          />
          {form.calculation === "PERCENT" ? (
            <TextField
              label={t("finance.table.percentValue")}
              value={form.percent}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, percent: event.target.value }))
              }
              inputMode="decimal"
              suffix="٪"
            />
          ) : (
            <TextField
              label={t("finance.table.fixedValue")}
              value={form.fixedToman}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, fixedToman: event.target.value }))
              }
              inputMode="numeric"
              suffix={t("finance.unit.toman")}
            />
          )}
        </div>
        <div className="m3-switch-row">
          <Switch
            checked={form.isActive}
            onChange={(checked) =>
              setForm((prev) => ({ ...prev, isActive: checked }))
            }
            label={t("finance.taxes.active")}
          />
          <Switch
            checked={form.isDefaultVat}
            onChange={(checked) =>
              setForm((prev) => ({ ...prev, isDefaultVat: checked }))
            }
            label={t("finance.table.defaultVat")}
          />
        </div>
        {error ? <ErrorState message={error} /> : null}
      </Dialog>
    </div>
  )
}
