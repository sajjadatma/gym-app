import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import {
  Building2,
  Copy,
  Mail,
  MapPin,
  Phone,
  Plus,
  ShieldCheck,
  Users,
} from "lucide-react"
import { useEffect, useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { type GymCreate, type GymCreated, GymsService } from "@/client"
import {
  Button,
  Dialog,
  EmptyState,
  PageHeader,
  SelectField,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

export function GymsPage() {
  const { t, formatNumber } = useI18n()
  const { gyms, isSuperuser, setActiveGym, isAdmin } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  useEffect(() => {
    if (isSuperuser) setActiveGym(null)
  }, [isSuperuser, setActiveGym])

  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<GymCreated | null>(null)
  const [form, setForm] = useState<GymCreate>({
    name: "",
    owner_email: "",
    owner_full_name: "",
    description: "",
    address: "",
    phone: "",
    activation_method: "invite",
    initial_password: "",
  })

  async function createGym() {
    setError(null)
    if (!form.name.trim()) {
      setError(t("validation.title"))
      return
    }
    if (!/^\S+@\S+\.\S+$/.test(form.owner_email)) {
      setError(t("validation.email"))
      return
    }
    if (
      form.activation_method === "password" &&
      form.initial_password &&
      form.initial_password.length < 8
    ) {
      setError(t("validation.initialPassword"))
      return
    }
    setLoading(true)
    try {
      const response = await GymsService.createGym({
        body: {
          ...form,
          name: form.name.trim(),
          initial_password:
            form.activation_method === "password"
              ? form.initial_password || null
              : null,
        },
      })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      setOpen(false)
      setCreated(response.data)
      setActiveGym(response.data.gym.id)
      show(t("gyms.created"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setLoading(false)
    }
  }

  async function copyPassword() {
    if (!created?.initial_password) return
    await navigator.clipboard.writeText(created.initial_password)
    show(t("common.success"), "success")
  }

  return (
    <>
      <PageHeader
        title={t("gyms.title")}
        subtitle={t("gyms.subtitle")}
        actions={
          isSuperuser ? (
            <Button icon={<Plus size={17} />} onClick={() => setOpen(true)}>
              {t("gyms.create")}
            </Button>
          ) : undefined
        }
      />

      {gyms.length === 0 ? (
        <EmptyState
          icon={<Building2 size={26} />}
          title={t("gyms.noGyms")}
          description={t("gyms.noGymsHint")}
          action={
            isSuperuser ? (
              <Button icon={<Plus size={17} />} onClick={() => setOpen(true)}>
                {t("gyms.create")}
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="m3-card-grid">
          {gyms.map((gym) => (
            <button
              key={gym.id}
              type="button"
              className="m3-entity-card"
              style={{ textAlign: "start", border: 0, fontFamily: "inherit" }}
              onClick={() => {
                setActiveGym(gym.id)
                navigate({ to: "/gyms/$gymId", params: { gymId: gym.id } })
              }}
            >
              <div className="m3-entity-card__head">
                <div>
                  <div className="m3-entity-card__title">{gym.name}</div>
                  <div className="m3-entity-card__meta">
                    <span>
                      <ShieldCheck
                        size={13}
                        style={{ verticalAlign: "middle" }}
                      />{" "}
                      {gym.owner_name ?? t("gyms.owner")}
                    </span>
                  </div>
                </div>
                <span
                  className={`m3-status ${
                    gym.is_active ? "m3-status--active" : "m3-status--inactive"
                  }`}
                >
                  {gym.is_active ? t("gyms.active") : t("gyms.inactive")}
                </span>
              </div>
              {gym.address ? (
                <div className="m3-entity-card__meta">
                  <span>
                    <MapPin size={13} style={{ verticalAlign: "middle" }} />{" "}
                    {gym.address}
                  </span>
                </div>
              ) : null}
              {gym.stats && isAdmin ? (
                <div className="m3-entity-card__meta">
                  <span>
                    <Users size={13} style={{ verticalAlign: "middle" }} />{" "}
                    {formatNumber(gym.stats.coaches)} {t("dashboard.coaches")}
                  </span>
                  <span>
                    <Users size={13} style={{ verticalAlign: "middle" }} />{" "}
                    {formatNumber(gym.stats.athletes)} {t("dashboard.athletes")}
                  </span>
                  <span>
                    {formatNumber(gym.stats.active_programs)}{" "}
                    {t("dashboard.activePrograms")}
                  </span>
                </div>
              ) : null}
              <div className="m3-entity-card__footer">
                <span className="m3-text-button">{t("gyms.enter")}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      <Dialog
        open={open}
        title={t("gyms.createTitle")}
        onClose={() => {
          setOpen(false)
          setError(null)
        }}
        footer={
          <>
            <Button variant="text" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={createGym} loading={loading}>
              {t("common.create")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? (
            <div className="m3-inline-alert" role="alert">
              {error}
            </div>
          ) : null}
          <TextField
            label={t("gyms.name")}
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            required
          />
          <div className="grid-2">
            <TextField
              label={t("gyms.ownerEmail")}
              type="email"
              dir="ltr"
              value={form.owner_email}
              onChange={(event) =>
                setForm({ ...form, owner_email: event.target.value })
              }
              required
            />
            <TextField
              label={t("gyms.ownerName")}
              value={form.owner_full_name ?? ""}
              onChange={(event) =>
                setForm({ ...form, owner_full_name: event.target.value })
              }
            />
          </div>
          <div className="grid-2">
            <TextField
              label={t("gyms.address")}
              value={form.address ?? ""}
              onChange={(event) =>
                setForm({ ...form, address: event.target.value })
              }
              leading={<MapPin size={17} />}
            />
            <TextField
              label={t("gyms.phone")}
              dir="ltr"
              value={form.phone ?? ""}
              onChange={(event) =>
                setForm({ ...form, phone: event.target.value })
              }
              leading={<Phone size={17} />}
            />
          </div>
          <TextField
            label={t("gyms.description")}
            value={form.description ?? ""}
            onChange={(event) =>
              setForm({ ...form, description: event.target.value })
            }
            multiline
            rows={2}
          />
          <SelectField
            label={t("gyms.activationMethod")}
            value={form.activation_method ?? "invite"}
            onChange={(value) =>
              setForm({
                ...form,
                activation_method: value as "invite" | "password",
              })
            }
            options={[
              { value: "invite", label: t("gyms.methodInvite") },
              { value: "password", label: t("gyms.methodPassword") },
            ]}
          />
          {form.activation_method === "password" ? (
            <TextField
              label={t("gyms.initialPassword")}
              type="text"
              dir="ltr"
              value={form.initial_password ?? ""}
              onChange={(event) =>
                setForm({ ...form, initial_password: event.target.value })
              }
              helper={t("gyms.initialPasswordHint")}
            />
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={Boolean(created)}
        title={t("gyms.created")}
        onClose={() => setCreated(null)}
        footer={
          <Button
            onClick={() => {
              setCreated(null)
              if (created) {
                navigate({
                  to: "/gyms/$gymId",
                  params: { gymId: created.gym.id },
                })
              }
            }}
          >
            {t("common.close")}
          </Button>
        }
      >
        {created ? (
          <div className="stack-sm">
            <p>{created.gym.name}</p>
            {created.invitation_sent ? (
              <div className="m3-inline-alert m3-inline-alert--info">
                <Mail
                  size={16}
                  style={{ verticalAlign: "middle", marginInlineEnd: 6 }}
                />
                {t("gyms.invitationSent")}
              </div>
            ) : null}
            {created.initial_password ? (
              <>
                <TextField
                  label={t("gyms.initialPassword")}
                  value={created.initial_password}
                  readOnly
                  dir="ltr"
                />
                <div className="row">
                  <Button
                    variant="outlined"
                    icon={<Copy size={16} />}
                    onClick={copyPassword}
                  >
                    {t("common.copy")}
                  </Button>
                </div>
                <p className="muted" style={{ fontSize: 12 }}>
                  {t("gyms.initialPasswordHint")}
                </p>
              </>
            ) : null}
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
