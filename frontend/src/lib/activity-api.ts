import { client } from "@/client/client.gen"
import type { ProgramRequest, TaxLine } from "@/lib/finance-api"

const api = client.instance
export type SetActual = {
  set_id: string
  completed: boolean
  reps: number | null
  weight_kg: number | null
}
export type SessionSet = SetActual & {
  exercise_id: string
  exercise_name: string
  set_number: number
  target_reps_min: number | null
  target_reps_max: number | null
  target_weight_kg: number | null
}
export type WorkoutSession = {
  id: string
  version_id: string | null
  day_id: string | null
  program_title: string
  day_title: string
  performed_on: string
  completed: boolean
  effort: number | null
  note: string | null
  sets: SessionSet[]
  created_at: string
}
export type SessionInput = {
  version_id: string
  day_id: string
  performed_on: string
  completed: boolean
  effort: number | null
  note: string | null
  sets: SetActual[]
  idempotency_key: string
}
export type CoachStatement = {
  gym_id: string
  earned_irr: number
  refunded_irr: number
  settled_irr: number
  pending_irr: number
  available_irr: number
  post_settlement_adjustments_irr: number
  simulated: boolean
  entries: {
    id: string
    description: string
    category: string
    earned_irr: number
    refunded_irr: number
    settled_irr: number
    pending_irr: number
    available_irr: number
    created_at: string
  }[]
  settlements: {
    id: string
    amount_irr: number
    status: string
    requested_at: string
    completed_at: string | null
  }[]
}
export type PurchaseDocument = {
  reference: string
  sale_id: string
  gym_name: string
  gym_address: string | null
  gym_phone: string | null
  athlete_name: string
  description: string
  issued_at: string
  base_amount_irr: number
  taxes: TaxLine[]
  tax_amount_irr: number
  total_amount_irr: number
  status: string
  refunded_irr: number
  simulated: boolean
  payments: {
    reference: string
    amount_irr: number
    paid_at: string | null
    status: string
  }[]
}
export type GymTasks = {
  requested_count: number
  in_progress_count: number
  without_program_count: number
  requests: ProgramRequest[]
  without_program: { id: string; name: string }[]
}
export async function getSessions(athleteId: string) {
  return (
    await api.get<WorkoutSession[]>(
      `/api/v1/athletes/${athleteId}/workout-sessions`,
    )
  ).data
}
export async function logSession(athleteId: string, body: SessionInput) {
  return (
    await api.post<WorkoutSession>(
      `/api/v1/athletes/${athleteId}/workout-sessions`,
      body,
    )
  ).data
}
export async function getCoachStatement(gymId: string) {
  return (
    await api.get<CoachStatement>(`/api/v1/gyms/${gymId}/coach/statement`)
  ).data
}
export async function getPurchaseDocument(gymId: string, saleId: string) {
  return (
    await api.get<PurchaseDocument>(
      `/api/v1/gyms/${gymId}/athlete/purchases/${saleId}/document`,
    )
  ).data
}
export async function getGymTasks(gymId: string) {
  return (await api.get<GymTasks>(`/api/v1/gyms/${gymId}/tasks`)).data
}
