export type Status = 'CRITICAL' | 'WARNING' | 'GREEN'
export type Availability = 'IN_STOCK' | 'LOW' | 'OUT'
export type AiMode = 'gemini' | 'mock'

export interface InventoryItem {
  medicine_name: string
  current_stock: number
  history: number[]
  projected_demand_7d: number
  avg_daily_demand: number
  days_to_stockout: number
  status: Status
  suggested_source_id: string | null
  suggested_source_name: string | null
}

export interface PhcRow {
  phc_id: string
  phc_name: string
  district: string
  state: string
  lat: number
  lng: number
  beds_available: number
  beds_total: number
  doctors_present: number
  doctors_total: number
  inventory: InventoryItem[]
}

export interface NetworkSummary {
  total_phcs: number
  active_stockout_alerts: number
  beds_available: number
  beds_total: number
  bed_availability_ratio: number
  active_ai_transfers: number
  ai_mode: AiMode
}

export interface NetworkStatus {
  summary: NetworkSummary
  phcs: PhcRow[]
}

export interface VoiceReportRequest {
  audio_transcript: string
  phc_id: string
  language: string
}

export interface VoiceReportResponse {
  source: AiMode
  fallback_reason: string | null
  phc_id: string
  extracted: {
    patient_count: number | null
    paracetamol_stock: number | null
    doctor_present: boolean | null
    emergency_notes: string
  }
  applied_to_network: boolean
}

export interface RedistributionRequest {
  source_phc_id: string
  target_phc_id: string
  item_name: string
  preview?: boolean
}

export interface Brief {
  transfer_quantity: number
  transport_mode: string
  route_priority: string
  emergency_justification: string
  estimated_travel_time: string
}

export interface RedistributionResponse {
  source: AiMode
  fallback_reason: string | null
  facts: Record<string, unknown>
  brief: Brief
}

export interface Transfer {
  id: string
  item: string
  source_phc_id: string
  source_phc_name: string | null
  target_phc_id: string
  target_phc_name: string | null
  quantity: number
  brief: Record<string, unknown>
  source: string
  created_at: string | null
}

export interface NearbyPhc {
  phc_id: string
  name: string
  district: string
  state: string
  distance_km: number
  beds_available: number
  beds_total: number
  doctors_present: number
  doctors_total: number
  maps_url: string
}

export interface MedicineAvailability {
  name: string
  availability: Availability
}

export interface PhcCard {
  type: 'phc'
  phc_id: string
  name: string
  district: string
  distance_km: number | null
  beds_available: number
  beds_total: number
  doctors_present: number
  doctors_total: number
  maps_url: string
  medicines: MedicineAvailability[]
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}

export interface ChatRequest {
  message: string
  history: ChatTurn[]
  location: { lat: number; lng: number } | null
  district_hint: string | null
}

export interface ChatResponse {
  reply: string
  emergency: boolean
  source: AiMode
  data_as_of: string
  cards: PhcCard[]
  suggestions: string[]
}