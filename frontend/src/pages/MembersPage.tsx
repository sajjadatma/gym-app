import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Copy,
  Mail,
  Pencil,
  Plus,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react"
import { useState } from "react"
import { translateApiError } from "@/api"
import { useAuth } from "@/auth"
import { GymsService, type MemberCreated, type MemberPublic } from "@/client"
import {
  Avatar,
  Button,
  Card,
  Chip,
  Dialog,
  EmptyState,
  ErrorState,
  PageHeader,
  SelectField,
  Spinner,
  StatusBadge,
  TextField,
} from "@/components/M3"
import { useI18n } from "@/i18n"
import { useSnackbar } from "@/snackbar"

type StaffRole = "GYM_ADMIN" | "COACH"

export function MembersPage() {
  const { t, formatDate } = useI18n()
  const { activeGym, activeGymId, isAdmin, me } = useAuth()
  const queryClient = useQueryClient()
  const { show } = useSnackbar()
  const [addOpen, setAddOpen] = useState(false)
  const [editMember, setEditMember] = useState<MemberPublic | null>(null)
  const [created, setCreated] = useState<MemberCreated | null>(null)
  const [roles, setRoles] = useState<StaffRole[]>(["COACH"])
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    phone: "",
    activation_method: "invite" as "invite" | "password",
    initial_password: "",
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const membersQuery = useQuery({
    queryKey: ["members", activeGymId],
    queryFn: async () =>
      (
        await GymsService.listMembers({
          path: { gym_id: activeGymId! },
        })
      ).data.data,
    enabled: Boolean(activeGymId && isAdmin),
  })

  if (!activeGym) {
    return (
      <PageHeader
        title={t("members.title")}
        subtitle={t("context.noGymHint")}
      />
    )
  }

  if (!isAdmin) {
    return (
      <>
        <PageHeader
          title={t("members.title")}
          subtitle={t("members.subtitle")}
        />
        <ErrorState message={t("errors.gym_admin_required")} />
      </>
    )
  }

  if (membersQuery.isLoading) return <Spinner label={t("common.loading")} />
  if (membersQuery.isError) {
    return (
      <ErrorState
        message={translateApiError(membersQuery.error, t)}
        retryLabel={t("common.retry")}
        onRetry={() => membersQuery.refetch()}
      />
    )
  }

  const members = (membersQuery.data ?? []).filter(
    (member) =>
      member.is_owner || member.roles.some((role) => role !== "ATHLETE"),
  )

  function toggleRole(role: StaffRole) {
    setRoles((current) =>
      current.includes(role)
        ? current.filter((item) => item !== role)
        : [...current, role],
    )
  }

  async function addMember() {
    setError(null)
    if (!/^\S+@\S+\.\S+$/.test(form.email)) {
      setError(t("validation.email"))
      return
    }
    if (!roles.length) {
      setError(t("errors.at_least_one_role_required"))
      return
    }
    if (roles.includes("COACH") && !form.phone.trim()) {
      setError(t("validation.coachPhone"))
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
    setSaving(true)
    try {
      const response = await GymsService.createMember({
        path: { gym_id: activeGymId! },
        body: {
          email: form.email,
          full_name: form.full_name || null,
          phone: form.phone.trim() || null,
          roles,
          activation_method: form.activation_method,
          initial_password:
            form.activation_method === "password"
              ? form.initial_password || null
              : null,
        },
      })
      await queryClient.invalidateQueries({
        queryKey: ["members", activeGymId],
      })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      setAddOpen(false)
      setCreated(response.data)
      setForm({
        email: "",
        full_name: "",
        phone: "",
        activation_method: "invite",
        initial_password: "",
      })
      setRoles(["COACH"])
      show(t("members.created"), "success")
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function updateMember(member: MemberPublic, nextRoles?: StaffRole[]) {
    setSaving(true)
    setError(null)
    try {
      await GymsService.updateMember({
        path: { gym_id: activeGymId!, membership_id: member.membership_id },
        body: {
          roles: nextRoles ?? member.roles.filter((role) => role !== "ATHLETE"),
        },
      })
      await queryClient.invalidateQueries({
        queryKey: ["members", activeGymId],
      })
      await queryClient.invalidateQueries({ queryKey: ["gyms"] })
      show(t("members.updated"), "success")
      setEditMember(null)
    } catch (err) {
      setError(translateApiError(err, t))
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(member: MemberPublic) {
    setSaving(true)
    setError(null)
    try {
      await GymsService.updateMember({
        path: { gym_id: activeGymId!, membership_id: member.membership_id },
        body: { is_active: !member.is_active },
      })
      await queryClient.invalidateQueries({
        queryKey: ["members", activeGymId],
      })
      show(t("members.updated"), "success")
    } catch (err) {
      show(translateApiError(err, t), "error")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <PageHeader
        title={t("members.title")}
        subtitle={`${activeGym.name} · ${t("members.subtitle")}`}
        actions={
          <Button icon={<Plus size={17} />} onClick={() => setAddOpen(true)}>
            {t("members.add")}
          </Button>
        }
      />

      {members.length === 0 ? (
        <EmptyState
          icon={<Users size={26} />}
          title={t("members.noMembers")}
          action={
            <Button icon={<Plus size={17} />} onClick={() => setAddOpen(true)}>
              {t("members.add")}
            </Button>
          }
        />
      ) : (
        <Card className="m3-card--outlined">
          <div className="m3-table-wrap">
            <table className="m3-table">
              <thead>
                <tr>
                  <th>{t("athletes.fullName")}</th>
                  <th>{t("auth.email")}</th>
                  <th>{t("members.roles")}</th>
                  <th>{t("status.active")}</th>
                  <th>{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.membership_id}>
                    <td>
                      <div
                        className="row"
                        style={{ gap: 10, flexWrap: "nowrap" }}
                      >
                        <Avatar name={member.full_name ?? member.email} />
                        <div>
                          <div style={{ fontWeight: 650 }}>
                            {member.full_name ?? member.email}
                            {member.user_id === me?.id ? (
                              <span className="muted" style={{ fontSize: 10 }}>
                                {" "}
                                ({t("members.self")})
                              </span>
                            ) : null}
                          </div>
                          <div className="muted" style={{ fontSize: 10.5 }}>
                            {formatDate(member.created_at)}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td dir="ltr" style={{ textAlign: "start" }}>
                      {member.email}
                    </td>
                    <td>
                      <div className="row" style={{ gap: 4 }}>
                        {member.is_owner ? (
                          <span className="m3-status m3-status--active">
                            <ShieldCheck size={12} /> {t("members.owner")}
                          </span>
                        ) : null}
                        {member.roles
                          .filter((role) => role !== "ATHLETE")
                          .map((role) => (
                            <span key={role} className="m3-chip">
                              {role === "GYM_ADMIN"
                                ? t("members.admin")
                                : t("members.coach")}
                            </span>
                          ))}
                        {!member.is_owner &&
                        member.roles.every((role) => role === "ATHLETE") ? (
                          <span className="m3-chip">
                            {t("context.athlete")}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      <StatusBadge
                        status={member.is_active ? "active" : "inactive"}
                      />
                    </td>
                    <td>
                      <div
                        className="row"
                        style={{ gap: 4, flexWrap: "nowrap" }}
                      >
                        {!member.is_owner ? (
                          <Button
                            variant="text"
                            size="sm"
                            icon={<Pencil size={14} />}
                            onClick={() => {
                              setError(null)
                              setEditMember(member)
                              setRoles(
                                member.roles.filter(
                                  (role): role is StaffRole =>
                                    role !== "ATHLETE",
                                ),
                              )
                            }}
                          >
                            {t("common.edit")}
                          </Button>
                        ) : null}
                        {!member.is_owner && member.user_id !== me?.id ? (
                          <Button
                            variant="text"
                            size="sm"
                            disabled={saving}
                            onClick={() => toggleActive(member)}
                          >
                            {member.is_active
                              ? t("members.deactivate")
                              : t("members.reactivate")}
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Dialog
        open={addOpen}
        title={t("members.addTitle")}
        onClose={() => setAddOpen(false)}
        footer={
          <>
            <Button variant="text" onClick={() => setAddOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={addMember} loading={saving}>
              {t("common.add")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <TextField
            label={t("auth.email")}
            type="email"
            dir="ltr"
            value={form.email}
            onChange={(event) =>
              setForm({ ...form, email: event.target.value })
            }
            required
          />
          <TextField
            label={t("athletes.fullName")}
            value={form.full_name}
            onChange={(event) =>
              setForm({ ...form, full_name: event.target.value })
            }
          />
          <TextField
            label={t("profile.phone")}
            type="tel"
            dir="ltr"
            value={form.phone}
            onChange={(event) =>
              setForm({ ...form, phone: event.target.value })
            }
            helper={
              roles.includes("COACH") ? t("members.coachPhoneHint") : undefined
            }
            required={roles.includes("COACH")}
          />
          <div>
            <div className="m3-field__label" style={{ marginBottom: 8 }}>
              {t("members.roles")}
            </div>
            <div className="row">
              <Chip
                selected={roles.includes("COACH")}
                onClick={() => toggleRole("COACH")}
              >
                {t("members.coach")}
              </Chip>
              <Chip
                selected={roles.includes("GYM_ADMIN")}
                onClick={() => toggleRole("GYM_ADMIN")}
                icon={<ShieldCheck size={14} />}
              >
                {t("members.admin")}
              </Chip>
            </div>
          </div>
          <SelectField
            label={t("gyms.activationMethod")}
            value={form.activation_method}
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
              value={form.initial_password}
              onChange={(event) =>
                setForm({ ...form, initial_password: event.target.value })
              }
              helper={t("gyms.initialPasswordHint")}
            />
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={Boolean(editMember)}
        title={t("members.roles")}
        onClose={() => setEditMember(null)}
        footer={
          <>
            <Button variant="text" onClick={() => setEditMember(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              loading={saving}
              onClick={() => editMember && updateMember(editMember, roles)}
              disabled={!roles.length}
            >
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <div className="m3-inline-alert">{error}</div> : null}
          <p className="muted">{editMember?.full_name ?? editMember?.email}</p>
          <div className="row">
            <Chip
              selected={roles.includes("COACH")}
              onClick={() => toggleRole("COACH")}
            >
              {t("members.coach")}
            </Chip>
            <Chip
              selected={roles.includes("GYM_ADMIN")}
              onClick={() => toggleRole("GYM_ADMIN")}
              icon={<ShieldCheck size={14} />}
            >
              {t("members.admin")}
            </Chip>
          </div>
          {!roles.length ? (
            <p className="text-error" style={{ fontSize: 12 }}>
              {t("errors.at_least_one_role_required")}
            </p>
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={Boolean(created)}
        title={t("members.created")}
        onClose={() => setCreated(null)}
        footer={
          <Button onClick={() => setCreated(null)}>{t("common.close")}</Button>
        }
      >
        {created ? (
          <div className="stack-sm">
            <div className="row">
              <UserRound size={18} />
              <strong>
                {created.member.full_name ?? created.member.email}
              </strong>
            </div>
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
                <Button
                  variant="outlined"
                  icon={<Copy size={16} />}
                  onClick={async () => {
                    await navigator.clipboard.writeText(
                      created.initial_password!,
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
          </div>
        ) : null}
      </Dialog>
    </>
  )
}
