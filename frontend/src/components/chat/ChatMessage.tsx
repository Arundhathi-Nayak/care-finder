import type { ChatResponse } from '../../types/api'
import PhcCard from './PhcCard'

export interface ChatMsg {
  id: number
  role: 'user' | 'assistant'
  text: string
  resp?: ChatResponse
}

interface Props {
  msg: ChatMsg
  onAsk: (text: string) => void
  busy: boolean
}

function asOf(iso: string): string {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ChatMessage({ msg, onAsk, busy }: Props) {
  if (msg.role === 'user') {
    return (
      <div className="d-flex justify-content-end mb-3">
        <div className="bg-success text-white rounded-3 px-3 py-2" style={{ maxWidth: '85%', whiteSpace: 'pre-wrap' }}>
          {msg.text}
        </div>
      </div>
    )
  }

  const r = msg.resp
  return (
    <div className="mb-3" style={{ maxWidth: '95%' }}>
      {r?.emergency && (
        <div className="alert alert-danger border-danger mb-2" role="alert">
          <div className="fw-bold mb-2">Emergency: call now</div>
          <div className="d-flex gap-2">
            <a className="btn btn-danger btn-lg flex-fill" href="tel:108">Call 108 (Ambulance)</a>
            <a className="btn btn-outline-danger btn-lg flex-fill" href="tel:112">Call 112</a>
          </div>
        </div>
      )}
      <div className="bg-white border rounded-3 px-3 py-2 mb-2" style={{ whiteSpace: 'pre-wrap' }}>
        {msg.text}
      </div>
      {r?.cards.map((c) => <PhcCard key={c.phc_id} card={c} onAsk={onAsk} disabled={busy} />)}
      {r && (
        <div className="text-muted small">
          {asOf(r.data_as_of) && <>Data as of {asOf(r.data_as_of)} · demo data</>}
          {r.source === 'mock' && !r.emergency && (
            <span className="badge text-bg-light border ms-2">Basic mode</span>
          )}
        </div>
      )}
    </div>
  )
}