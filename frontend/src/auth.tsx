import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react"
import { getApiErrorDetail } from "./api"
import type { GymPublic, UserMePublic } from "./client"
import { GymsService, LoginService, UsersService } from "./client"

type RoleMode = "GYM_ADMIN" | "COACH" | "ATHLETE"

type AuthContextValue = {
  token: string | null
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
  logout: () => void
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
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("access_token"),
  )
  const [activeGymId, setActiveGymIdState] = useState<string | null>(() =>
    localStorage.getItem("gym.activeGymId"),
  )
  const [activeRole, setActiveRoleState] = useState<RoleMode | null>(() => {
    const stored = localStorage.getItem("gym.activeRole")
    return ROLE_ORDER.includes(stored as RoleMode) ? (stored as RoleMode) : null
  })

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: async () => (await UsersService.readUserMe()).data,
    enabled: Boolean(token),
    retry: false,
  })

  const gymsQuery = useQuery({
    queryKey: ["gyms"],
    queryFn: async () => (await GymsService.listGyms()).data.data,
    enabled: Boolean(token),
    retry: false,
  })

  const me = meQuery.data ?? null
  const gyms = gymsQuery.data ?? []
  const activeGym = gyms.find((gym) => gym.id === activeGymId) ?? null

  useEffect(() => {
    if (!token) return
    const error = meQuery.error ?? gymsQuery.error
    if (!error) return
    const detail = getApiErrorDetail(error)
    if (
      ["invalid_credentials", "invalid_token", "user_not_found"].includes(
        detail ?? "",
      )
    ) {
      localStorage.removeItem("access_token")
      setToken(null)
    }
  }, [token, meQuery.error, gymsQuery.error])

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
  useEffect(() => {
    if (!activeGym) return
    const roles = activeGym.my_roles.filter((role): role is RoleMode =>
      ROLE_ORDER.includes(role as RoleMode),
    )
    if (!roles.length) return
    if (!activeRole || !roles.includes(activeRole)) {
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
      const response = await LoginService.loginAccessToken({
        body: { username: email, password },
      })
      localStorage.removeItem("gym.activeGymId")
      localStorage.removeItem("gym.activeRole")
      setActiveGymIdState(null)
      setActiveRoleState(null)
      localStorage.setItem("access_token", response.data.access_token)
      setToken(response.data.access_token)
      await queryClient.invalidateQueries()
    },
    [queryClient],
  )

  const logout = useCallback(() => {
    localStorage.removeItem("access_token")
    setToken(null)
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
    token,
    me,
    gyms,
    activeGym,
    activeGymId,
    activeRole: effectiveRole,
    availableRoles,
    isLoading: Boolean(token) && (meQuery.isLoading || gymsQuery.isLoading),
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
