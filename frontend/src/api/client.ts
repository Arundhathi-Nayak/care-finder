import type {
  ChatRequest, ChatResponse, NearbyPhc, NetworkStatus, RedistributionRequest,
  RedistributionResponse, Transfer, VoiceReportRequest, VoiceReportResponse,
} from '../types/api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw new ApiError('Cannot reach the server. Please check your connection and try again.', 0)
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') msg = body.detail
      else if (Array.isArray(body.detail)) {
        msg = body.detail.map((d: { msg?: string }) => d.msg ?? 'Invalid input').join('; ')
      }
    } catch {
      /* body was not JSON; keep the generic message */
    }
    throw new ApiError(msg, res.status)
  }
  return (await res.json()) as T
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const getNetworkStatus = () => request<NetworkStatus>('/api/v1/network-status')
export const postVoiceReport = (b: VoiceReportRequest) =>
  post<VoiceReportResponse>('/api/v1/log-daily-voice-report', b)
export const postRedistribution = (b: RedistributionRequest) =>
  post<RedistributionResponse>('/api/v1/recommend-redistribution', b)
export const getTransfers = (limit = 20) => request<Transfer[]>(`/api/v1/transfers?limit=${limit}`)
export const getNearbyPhcs = (lat: number, lng: number, radiusKm = 50, limit = 5) =>
  request<NearbyPhc[]>(`/api/v1/phcs/nearby?lat=${lat}&lng=${lng}&radius_km=${radiusKm}&limit=${limit}`)
export const postChat = (b: ChatRequest) => post<ChatResponse>('/api/v1/chat', b)