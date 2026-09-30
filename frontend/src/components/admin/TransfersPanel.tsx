import type { Transfer } from '../../types/api'

interface Props {
  transfers: Transfer[] | null
  error: string | null
  loading: boolean
}

export function timeAgo(iso: string | null): string {
  if (!iso) return 'just now'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}

export default function TransfersPanel({ transfers, error, loading }: Props) {
  return (
    <div className="card shadow-sm h-100">
      <div className="card-header bg-white fw-semibold">Recent AI transfers</div>
      <div className="list-group list-group-flush">
        {error && <div className="list-group-item text-danger small">{error}</div>}
        {!error && loading && !transfers && <div className="list-group-item text-muted">Loading…</div>}
        {transfers && transfers.length === 0 && (
          <div className="list-group-item text-muted">No transfers yet. Dispatch a CRITICAL item to see one here.</div>
        )}
        {transfers?.map((t) => (
          <div className="list-group-item" key={t.id}>
            <div className="d-flex justify-content-between">
              <span className="fw-semibold">{t.item}</span>
              <span className="badge text-bg-primary">{t.quantity} units</span>
            </div>
            <div className="small">
              {t.source_phc_name ?? t.source_phc_id} → {t.target_phc_name ?? t.target_phc_id}
            </div>
            <div className="text-muted small">{timeAgo(t.created_at)} · {t.source}</div>
          </div>
        ))}
      </div>
    </div>
  )
}