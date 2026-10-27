import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  ArrowRight,
  Building2,
  Copy,
  Crown,
  ImagePlus,
  Mail,
  MapPin,
  Palette,
  Pencil,
  Phone,
  ShieldCheck,
  Trash2,
  UserRound,
  Users,
} from "lucide-react"
import { type CSSProperties, useEffect, useRef, useState } from "react"
import { apiAssetUrl, translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { GymsService, type OwnershipTransferred } from "@/client"
import {
  Button,
  Card,
  Dialog,
  ErrorState,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { readableOnColor } from "@/lib/brand"
import { useSnackbar } from "@/snackbar"

export function GymDetailPage({ gymId }: { gymId: string }) {
  const { t, formatNumber, formatDate } = useI18n()
  const { isSuperuser, isOwner, me, activeGymId, setActiveGym } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const gymQuery = useQuery({
    queryKey: ["gym", gymId],
    queryFn: async () =>
      (await GymsService.readGym({ path: { gym_id: gymId } })).data,
  })
  const [editOpen, setEditOpen] = useState(false)
  const [transferOpen, setTransferOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [transferred, setTransferred] = useState<OwnershipTransferred | null>(
    null,
  )
  const [editForm, setEditForm] = useState({
    name: "",
    description: "",
    address: "",
    phone: "",
    is_active: true,
  })
  const [transferForm, setTransferForm] = useState({
    new_owner_email: "",
    new_owner_full_name: "",
    activation_method: "invite" as "invite" | "password",
    initial_password: "",
  })
  const [brandingOpen, setBrandingOpen] = useState(false)
  const [brandSaving, setBrandSaving] = useState(false)
  const [brandError, setBrandError] = useState<string | null>(null)
  const [brandForm, setBrandForm] = useState({ primary: "", accent: "" })
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [removeLogo, setRemoveLogo] = useState(false)
  const logoInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    return () => {
      if (logoPreview) URL.revokeObjectURL(logoPreview)
    }
  }, [logoPreview])

  const gym = gymQuery.data

  useEffect(() => {
    if (gym && activeGymId !== gym.id) setActiveGym(gym.id)
  }, [gym, activeGymId, setActiveGym])

  if (gymQuery.isLoading) return <Spinner label={t("common.loading")} />
  if (gymQuery.isError || !gym) {
    return (
      <ErrorState
        message={translateApiError(gymQuery.error, t)}
        onRetry={() => gymQuery.refetch()}
        retryLabel={t("common.retry")}
      />
    )
  }

  const canTransfer = isSuperuser || gym.owner_id === me?.id || isOwner
  const canManage =
    isSuperuser || gym.my_roles.includes("GYM_ADMIN") || gym.is_owner

  function openEdit() {
    setEditForm({
      name: gym!.name,
      description: gym!.description ?? "",
      address: gym!.address ?? "",
      phone: gym!.phone ?? "",
      is_active: gym!.is_active,
    })
    setEditOpen(true)
  }

  async function saveEdit() {
    setSaving(true)
    setError(null)
    try {
      await GymsService.updateGym({
        path: { gym_id: gymId },
        body: {
          name: editForm.name,
          description: editForm.description || null,
          address: editForm.address || null,
          phone: editForm.phone || null,
          is_active: isSuperuser ? editForm.is_active : undefined,
        },
      })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      await queryClient.invalidateQueries({ queryKey: ["gym", gymId] })
      setEditOpen(false)
      show(t("gyms.updated"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  function openBranding() {
    if (!gym) return
    if (logoInputRef.current) logoInputRef.current.value = ""
    setBrandForm({
      primary: gym.brand_primary_color ?? "",
      accent: gym.brand_accent_color ?? "",
    })
    setLogoFile(null)
    setLogoPreview(null)
    setRemoveLogo(false)
    setBrandError(null)
    setBrandingOpen(true)
  }

  function selectLogo(file: File | null) {
    setBrandError(null)
    if (!file) return
    if (!["image/png", "image/jpeg"].includes(file.type)) {
      setBrandError(t("branding.logoType"))
      if (logoInputRef.current) logoInputRef.current.value = ""
      return
    }
    if (file.size > 512 * 1024) {
      setBrandError(t("branding.logoSize"))
      if (logoInputRef.current) logoInputRef.current.value = ""
      return
    }
    if (logoPreview) URL.revokeObjectURL(logoPreview)
    setLogoFile(file)
    setLogoPreview(URL.createObjectURL(file))
    setRemoveLogo(false)
    if (logoInputRef.current) logoInputRef.current.value = ""
  }

  async function saveBranding() {
    setBrandSaving(true)
    setBrandError(null)
    const colorPattern = /^#[0-9a-f]{6}$/i
    if (
      (brandForm.primary && !colorPattern.test(brandForm.primary)) ||
      (brandForm.accent && !colorPattern.test(brandForm.accent))
    ) {
      setBrandError(t("branding.invalidColor"))
      setBrandSaving(false)
      return
    }
    try {
      await GymsService.updateGym({
        path: { gym_id: gymId },
        body: {
          brand_primary_color: brandForm.primary || null,
          brand_accent_color: brandForm.accent || null,
        },
      })
      if (removeLogo) {
        await GymsService.deleteGymBrandingLogo({
          path: { gym_id: gymId },
        })
      } else if (logoFile) {
        await GymsService.uploadBrandingLogo({
          path: { gym_id: gymId },
          body: { file: logoFile },
        })
      }
      setBrandingOpen(false)
      setLogoFile(null)
      setLogoPreview(null)
      show(t("branding.updated"), "success")
    } catch (err) {
      setBrandError(translateApiError(err, t))
    } finally {
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      await queryClient.invalidateQueries({ queryKey: ["gym", gymId] })
      setBrandSaving(false)
    }
  }

  async function transfer() {
    setSaving(true)
    setError(null)
    try {
      const response = await GymsService.transferOwnership({
        path: { gym_id: gymId },
        body: {
          new_owner_email: transferForm.new_owner_email,
          new_owner_full_name: transferForm.new_owner_full_name || null,
          activation_method: transferForm.activation_method,
          initial_password:
            transferForm.activation_method === "password"
              ? transferForm.initial_password || null
              : null,
        },
      })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      await queryClient.invalidateQueries({ queryKey: ["gym", gymId] })
      setTransferOpen(false)
      setTransferred(response.data)
      show(t("gyms.transferred"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={gym.name}
        subtitle={gym.description ?? t("gyms.details")}
        onBack={() => navigate({ to: "/gyms/$gymId", params: { gymId } })}
        backLabel={t("gyms.backToWorkspace")}
        actions={
          canManage ? (
            <>
              <Button
                variant="outlined"
                icon={<Pencil size={16} />}
                onClick={openEdit}
              >
                {t("common.edit")}
              </Button>
              {canTransfer ? (
                <Button
                  variant="tonal"
                  icon={<Crown size={16} />}
                  onClick={() => setTransferOpen(true)}
                >
                  {t("gyms.transfer")}
                </Button>
              ) : null}
            </>
          ) : undefined
        }
      />

      <div className="grid-2">
        <Card>
          <div className="m3-section__header">
            <div>
              <h2 className="m3-section__title">{t("gyms.details")}</h2>
              <p className="m3-section__subtitle">
                {gym.is_active ? t("gyms.active") : t("gyms.inactive")}
              </p>
            </div>
            <Building2 size={22} className="muted" />
          </div>
          <div className="stack-sm">
            <div className="row">
              <Crown size={17} className="muted" />
              <span className="muted">{t("gyms.owner")}:</span>
              <strong>{gym.owner_name ?? "—"}</strong>
            </div>
            {gym.address ? (
              <div className="row">
                <MapPin size={17} className="muted" />
                <span>{gym.address}</span>
              </div>
            ) : null}
            {gym.phone ? (
              <div className="row">
                <Phone size={17} className="muted" />
                <span dir="ltr">{gym.phone}</span>
              </div>
            ) : null}
            <div className="row">
              <ShieldCheck size={17} className="muted" />
              <span className="muted">{t("common.create")}:</span>
              <span>{formatDate(gym.created_at)}</span>
            </div>
          </div>
        </Card>

        {gym.stats && canManage ? (
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("dashboard.title")}</h2>
                <p className="m3-section__subtitle">
                  {t("dashboard.adminSubtitle")}
                </p>
              </div>
            </div>
            <div className="m3-stat-grid">
              <div className="m3-stat">
                <div className="m3-stat__label">{t("gyms.totalCoaches")}</div>
                <div className="m3-stat__value">
                  {formatNumber(gym.stats.coaches)}
                </div>
              </div>
              <div className="m3-stat">
                <div className="m3-stat__label">{t("gyms.totalAthletes")}</div>
                <div className="m3-stat__value">
                  {formatNumber(gym.stats.athletes)}
                </div>
              </div>
              <div className="m3-stat">
                <div className="m3-stat__label">{t("gyms.activePrograms")}</div>
                <div className="m3-stat__value">
                  {formatNumber(gym.stats.active_programs)}
                </div>
              </div>
              <div className="m3-stat">
                <div className="m3-stat__label">{t("gyms.draftPrograms")}</div>
                <div className="m3-stat__value">
                  {formatNumber(gym.stats.draft_programs)}
                </div>
              </div>
              <div className="m3-stat">
                <div className="m3-stat__label">
                  {t("gyms.archivedPrograms")}
                </div>
                <div className="m3-stat__value">
                  {formatNumber(gym.stats.archived_programs)}
                </div>
              </div>
            </div>
            <div className="row" style={{ marginTop: 16 }}>
              <Button
                variant="tonal"
                icon={<Users size={16} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/members",
                    params: { gymId },
                  })
                }
              >
                {t("nav.members")}
              </Button>
              <Button
                variant="outlined"
                icon={<UserRound size={16} />}
                onClick={() =>
                  navigate({
                    to: "/gyms/$gymId/athletes",
                    params: { gymId },
                  })
                }
              >
                {t("nav.athletes")}
              </Button>
            </div>
          </Card>
        ) : null}

        {canManage ? (
          <Card>
            <div className="m3-section__header">
              <div>
                <h2 className="m3-section__title">{t("branding.title")}</h2>
                <p className="m3-section__subtitle">{t("branding.subtitle")}</p>
              </div>
              <Palette size={22} className="muted" />
            </div>
            <div
              className="club-brand-preview"
              style={
                {
                  "--club-primary":
                    gym.brand_primary_color ?? "var(--m3-primary)",
                  "--club-on-primary": gym.brand_primary_color
                    ? readableOnColor(gym.brand_primary_color)
                    : "var(--m3-on-primary)",
                } as CSSProperties
              }
            >
              <div className="club-brand-preview__mark">
                {gym.logo_url ? (
                  <img
                    className="club-brand-preview__logo"
                    src={apiAssetUrl(gym.logo_url)}
                    alt={t("branding.logo")}
                    onError={(event) => {
                      event.currentTarget.style.display = "none"
                    }}
                  />
                ) : (
                  "A"
                )}
              </div>
              <div>
                <div className="club-brand-preview__name">{gym.name}</div>
                <div className="club-brand-preview__colors">
                  {gym.brand_primary_color ? (
                    <span
                      className="club-swatch"
                      style={{ background: gym.brand_primary_color }}
                      title={t("branding.primary")}
                    />
                  ) : null}
                  {gym.brand_accent_color ? (
                    <span
                      className="club-swatch"
                      style={{ background: gym.brand_accent_color }}
                      title={t("branding.accent")}
                    />
                  ) : null}
                  {!gym.brand_primary_color && !gym.brand_accent_color ? (
                    <span className="muted">{t("branding.defaultColors")}</span>
                  ) : null}
                </div>
              </div>
            </div>
            <div className="row" style={{ marginTop: 14 }}>
              <Button
                variant="outlined"
                icon={<Palette size={16} />}
                onClick={openBranding}
              >
                {t("branding.edit")}
              </Button>
            </div>
          </Card>
        ) : null}
      </div>

      <Dialog
        open={brandingOpen}
        title={t("branding.edit")}
        description={t("branding.scopeHint")}
        onClose={() => {
          if (brandSaving) return
          setBrandingOpen(false)
          setBrandError(null)
        }}
        footer={
          <>
            <Button
              variant="text"
              disabled={brandSaving}
              onClick={() => setBrandingOpen(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button onClick={saveBranding} loading={brandSaving}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {brandError ? (
            <div className="m3-inline-alert" role="alert">
              {brandError}
            </div>
          ) : null}
          <input
            ref={logoInputRef}
            type="file"
            accept="image/png,image/jpeg"
            hidden
            onChange={(event) => selectLogo(event.target.files?.[0] ?? null)}
          />
          <div>
            <div className="m3-field__label">{t("branding.logo")}</div>
            <div className="club-brand-preview" style={{ marginTop: 6 }}>
              <div
                className="club-brand-preview__mark"
                style={{
                  background: brandForm.primary || undefined,
                  color: brandForm.primary
                    ? readableOnColor(brandForm.primary)
                    : undefined,
                }}
              >
                {logoPreview || (!removeLogo && gym.logo_url) ? (
                  <img
                    className="club-brand-preview__logo"
                    src={
                      logoPreview ??
                      (!removeLogo ? apiAssetUrl(gym.logo_url) : undefined)
                    }
                    alt={t("branding.logoPreview")}
                  />
                ) : (
                  "A"
                )}
              </div>
              <div className="row">
                <Button
                  variant="outlined"
                  size="sm"
                  icon={<ImagePlus size={15} />}
                  onClick={() => logoInputRef.current?.click()}
                >
                  {t("branding.chooseLogo")}
                </Button>
                {gym.logo_url || logoFile ? (
                  <Button
                    variant="text"
                    size="sm"
                    icon={<Trash2 size={15} />}
                    onClick={() => {
                      setLogoFile(null)
                      if (logoPreview) URL.revokeObjectURL(logoPreview)
                      setLogoPreview(null)
                      setRemoveLogo(true)
                    }}
                  >
                    {t("branding.removeLogo")}
                  </Button>
                ) : null}
              </div>
            </div>
            <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
              {t("branding.logoHint")}
            </p>
          </div>

          <div className="brand-color-grid">
            <div className="brand-color-row">
              <input
                type="color"
                aria-label={t("branding.primary")}
                value={brandForm.primary || "#006c51"}
                onChange={(event) =>
                  setBrandForm({ ...brandForm, primary: event.target.value })
                }
              />
              <TextField
                label={t("branding.primary")}
                value={brandForm.primary}
                dir="ltr"
                placeholder="#006c51"
                onChange={(event) =>
                  setBrandForm({ ...brandForm, primary: event.target.value })
                }
              />
            </div>
            <div className="brand-color-row">
              <input
                type="color"
                aria-label={t("branding.accent")}
                value={brandForm.accent || "#006c51"}
                onChange={(event) =>
                  setBrandForm({ ...brandForm, accent: event.target.value })
                }
              />
              <TextField
                label={t("branding.accent")}
                value={brandForm.accent}
                dir="ltr"
                placeholder="#006c51"
                onChange={(event) =>
                  setBrandForm({ ...brandForm, accent: event.target.value })
                }
              />
            </div>
          </div>
          <div className="row">
            <Button
              variant="text"
              size="sm"
              onClick={() => setBrandForm({ primary: "", accent: "" })}
            >
              {t("branding.resetColors")}
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={editOpen}
        title={t("gyms.editTitle")}
        onClose={() => setEditOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setEditOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={saveEdit} loading={saving}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <TextField
            label={t("gyms.name")}
            value={editForm.name}
            onChange={(event) =>
              setEditForm({ ...editForm, name: event.target.value })
            }
            required
          />
          <TextField
            label={t("gyms.description")}
            value={editForm.description}
            onChange={(event) =>
              setEditForm({ ...editForm, description: event.target.value })
            }
            multiline
            rows={2}
          />
          <div className="grid-2">
            <TextField
              label={t("gyms.address")}
              value={editForm.address}
              onChange={(event) =>
                setEditForm({ ...editForm, address: event.target.value })
              }
            />
            <TextField
              label={t("gyms.phone")}
              value={editForm.phone}
              onChange={(event) =>
                setEditForm({ ...editForm, phone: event.target.value })
              }
              dir="ltr"
            />
          </div>
        </div>
      </Dialog>

      <Dialog
        open={transferOpen}
        title={t("gyms.transferTitle")}
        description={t("gyms.transferWarning")}
        onClose={() => setTransferOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setTransferOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={transfer} loading={saving}>
              {t("gyms.transfer")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <TextField
            label={t("gyms.newOwnerEmail")}
            type="email"
            dir="ltr"
            value={transferForm.new_owner_email}
            onChange={(event) =>
              setTransferForm({
                ...transferForm,
                new_owner_email: event.target.value,
              })
            }
            required
          />
          <TextField
            label={t("gyms.newOwnerName")}
            value={transferForm.new_owner_full_name}
            onChange={(event) =>
              setTransferForm({
                ...transferForm,
                new_owner_full_name: event.target.value,
              })
            }
          />
          <SelectField
            label={t("gyms.activationMethod")}
            value={transferForm.activation_method}
            onChange={(value) =>
              setTransferForm({
                ...transferForm,
                activation_method: value as "invite" | "password",
              })
            }
            options={[
              { value: "invite", label: t("gyms.methodInvite") },
              { value: "password", label: t("gyms.methodPassword") },
            ]}
          />
          {transferForm.activation_method === "password" ? (
            <TextField
              label={t("gyms.initialPassword")}
              type="text"
              dir="ltr"
              value={transferForm.initial_password}
              onChange={(event) =>
                setTransferForm({
                  ...transferForm,
                  initial_password: event.target.value,
                })
              }
              helper={t("gyms.initialPasswordHint")}
            />
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={Boolean(transferred)}
        title={t("gyms.transferred")}
        onClose={() => setTransferred(null)}
        footer={
          <Button onClick={() => setTransferred(null)}>
            {t("common.close")}
          </Button>
        }
      >
        {transferred ? (
          <div className="stack-sm">
            {transferred.invitation_sent ? (
              <div className="m3-inline-alert m3-inline-alert--info">
                <Mail
                  size={16}
                  style={{ verticalAlign: "middle", marginInlineEnd: 6 }}
                />
                {t("gyms.invitationSent")}
              </div>
            ) : null}
            {transferred.initial_password ? (
              <>
                <TextField
                  label={t("gyms.initialPassword")}
                  value={transferred.initial_password}
                  readOnly
                  dir="ltr"
                />
                <Button
                  variant="outlined"
                  icon={<Copy size={16} />}
                  onClick={async () => {
                    await navigator.clipboard.writeText(
                      transferred.initial_password!,
                    )
                    show(t("common.success"), "success")
                  }}
                >
                  {t("common.copy")}
                </Button>
                <p className="muted" style={{ fontSize: 12 }}>
                  {t("gyms.initialPasswordHint")}
                </p>
              </>
            ) : null}
            <Button
              variant="text"
              icon={<ArrowRight size={16} />}
              onClick={() => {
                setTransferred(null)
                navigate({ to: "/gyms" })
              }}
            >
              {t("gyms.title")}
            </Button>
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
