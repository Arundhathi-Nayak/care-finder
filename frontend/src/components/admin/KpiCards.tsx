import type { NetworkStatus } from '../../types/api'

interface Props {
  data: NetworkStatus | null
  loading: boolean
}

function Card({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="col-6 col-lg-3">
      <div className="card h-100 shadow-sm">
        <div className="card-body">
          <div className="text-muted small">{label}</div>
          <div className={`fs-2 fw-bold ${tone ?? ''}`}>{value}</div>
          {sub && <div className="text-muted small">{sub}</div>}
        </div>
      </div>
    </div>
  )
}

export default function KpiCards({ data, loading }: Props) {
  if (!data) {
    return (
      <div className="row g-3 mb-3">
        {[0, 1, 2, 3].map((i) => (
          <div className="col-6 col-lg-3" key={i}>
            <div className="card h-100 shadow-sm">
              <div className="card-body placeholder-glow">
                <span className="placeholder col-6 mb-2" />
                <span className="placeholder col-4 placeholder-lg" />
                {!loading && <div className="text-muted small">No data</div>}
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }
  const s = data.summary
  return (
    <>
      <div className="d-flex justify-content-end mb-2">
        <span className={`badge ${s.ai_mode === 'gemini' ? 'text-bg-success' : 'text-bg-secondary'}`}>
          AI mode: {s.ai_mode}
        </span>
      </div>
      <div className="row g-3 mb-3">
        <Card label="Total monitored PHCs" value={String(s.total_phcs)} />
        <Card
          label="Active stock-out alerts"
          value={String(s.active_stockout_alerts)}
          tone={s.active_stockout_alerts > 0 ? 'text-danger' : 'text-success'}
        />
        <Card
          label="Bed availability"
          value={`${Math.round(s.bed_availability_ratio * 100)}%`}
          sub={`${s.beds_available} / ${s.beds_total} beds`}
        />
        <Card label="Active AI transfers" value={String(s.active_ai_transfers)} />
      </div>
    </>
  )
}