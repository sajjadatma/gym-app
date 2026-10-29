import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import type { GymPublic, UserMePublic } from "./client"
import { GymsService, LoginService, UsersService } from "./client"

type RoleMode = "GYM_ADMIN" | "COACH" | "ATHLETE"

type AuthContextValue = {
  me: UserMePublic | null
  gyms: GymPublic[]
  activeGym: GymPublic | null
  activeGymId: string | null
  activeRole: RoleMode | null
  availableRoles: RoleMode[]
  isLoading: boolean
  isSuperuser: boolean
  isAdmin: boolean
  isCoach: boolean
  isAthlete: boolean
  isOwner: boolean
  mustChangePassword: boolean
  setActiveGym: (gymId: string | null) => void
  setActiveRole: (role: RoleMode) => void
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const ROLE_ORDER: RoleMode[] = ["GYM_ADMIN", "COACH", "ATHLETE"]

function pickDefaultRole(gym: GymPublic | null): RoleMode | null {
  if (!gym) return null
  for (const role of ROLE_ORDER) {
    if (gym.my_roles.includes(role)) return role
  }
  return null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [activeGymId, setActiveGymIdState] = useState<string | null>(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  // The header no longer exposes role switching. Derive the workspace role
  // from the member's highest assigned role instead of a stale stored value,
  // so a previous coach-mode selection cannot strand an admin.
  const [activeRole, setActiveRoleState] = useState<RoleMode | null>(null)

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await UsersService.readUserMe()).data,
    retry: false,
  })

  const gymsQuery = useQuery({
    queryKey: ["gyms"],
    queryFn: async () => (await GymsService.listGyms()).data.data,
    enabled: Boolean(meQuery.data),
    retry: false,
  })

  const me = meQuery.data ?? null
  const gyms = gymsQuery.data ?? []
  const activeGym = gyms.find((gym) => gym.id === activeGymId) ?? null

  useEffect(() => {
    if (
      me?.must_change_password &&
      window.location.pathname !== "/change-password"
    ) {
      window.location.assign("/change-password")
    }
  }, [me?.must_change_password])

  useEffect(() => {
    if (!gymsQuery.isSuccess || !me) return
    if (me.is_superuser) return
    if (gyms.length === 0) {
      if (activeGymId !== null) {
        localStorage.removeItem("gym.activeGymId")
        setActiveGymIdState(null)
      }
      return
    }
    if (!activeGymId || !gyms.some((gym) => gym.id === activeGymId)) {
      const first = gyms[0].id
      localStorage.setItem("gym.activeGymId", first)
      setActiveGymIdState(first)
    }
  }, [gyms, gymsQuery.isSuccess, activeGymId, me])

  const defaultRole = pickDefaultRole(activeGym)
  const roleGymId = useRef<string | null>(null)
  useEffect(() => {
    if (!activeGym) {
      roleGymId.current = null
      return
    }
    const roles = activeGym.my_roles.filter((role): role is RoleMode =>
      ROLE_ORDER.includes(role as RoleMode),
    )
    if (!roles.length) return
    const gymChanged = roleGymId.current !== activeGym.id
    roleGymId.current = activeGym.id
    if (gymChanged || !activeRole || !roles.includes(activeRole)) {
      const next = pickDefaultRole(activeGym)
      if (next) {
        localStorage.setItem("gym.activeRole", next)
        setActiveRoleState(next)
      }
    }
  }, [activeGym, activeRole])

  const setActiveGym = useCallback(
    (gymId: string | null) => {
      if (gymId === null) {
        localStorage.removeItem("gym.activeGymId")
        localStorage.removeItem("gym.activeRole")
        setActiveGymIdState(null)
        setActiveRoleState(null)
      } else {
        localStorage.setItem("gym.activeGymId", gymId)
        setActiveGymIdState(gymId)
      }
      queryClient.removeQueries({
        predicate: (query) =>
          !["me", "gyms"].includes(String(query.queryKey[0])),
      })
    },
    [queryClient],
  )

  const setActiveRole = useCallback((role: RoleMode) => {
    localStorage.setItem("gym.activeRole", role)
    setActiveRoleState(role)
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      await LoginService.loginAccessToken({
        body: { username: email, password },
      })
      localStorage.removeItem("gym.activeGymId")
      localStorage.removeItem("gym.activeRole")
      setActiveGymIdState(null)
      setActiveRoleState(null)
      await queryClient.invalidateQueries()
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    try {
      await LoginService.logout()
    } catch {
      // The cookie may already be expired; still return to the login screen.
    }
    queryClient.clear()
    window.location.assign("/login")
  }, [queryClient])

  const refresh = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["me"] }),
      queryClient.invalidateQueries({ queryKey: ["gyms"] }),
    ])
    await Promise.all([meQuery.refetch(), gymsQuery.refetch()])
  }, [queryClient, meQuery, gymsQuery])

  const availableRoles = useMemo<RoleMode[]>(() => {
    if (!activeGym) return []
    return activeGym.my_roles.filter((role): role is RoleMode =>
      ROLE_ORDER.includes(role as RoleMode),
    )
  }, [activeGym])

  const effectiveRole = activeRole ?? defaultRole
  const isSuperuser = Boolean(me?.is_superuser)
  const isAdmin = isSuperuser || effectiveRole === "GYM_ADMIN"
  const isCoach = effectiveRole === "COACH"
  const isAthlete = effectiveRole === "ATHLETE"

  const value: AuthContextValue = {
    me,
    gyms,
    activeGym,
    activeGymId,
    activeRole: effectiveRole,
    availableRoles,
    isLoading: meQuery.isLoading || (Boolean(me) && gymsQuery.isLoading),
    isSuperuser,
    isAdmin,
    isCoach,
    isAthlete,
    isOwner: Boolean(activeGym?.is_owner),
    mustChangePassword: Boolean(me?.must_change_password),
    setActiveGym,
    setActiveRole,
    login,
    logout,
    refresh,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used inside AuthProvider")
  return context
}

export type { RoleMode }
