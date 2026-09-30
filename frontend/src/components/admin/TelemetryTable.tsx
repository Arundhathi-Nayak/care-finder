import { useMemo, useState } from 'react'
import type { Status } from '../../types/api'
import Sparkline from './Sparkline'
import { formatDays, type Row } from './rows'

interface Props {
  rows: Row[]
  onDispatch: (row: Row) => void
}

const BADGE: Record<Status, string> = {
  CRITICAL: 'text-bg-danger',
  WARNING: 'text-bg-warning',
  GREEN: 'text-bg-success',
}

export default function TelemetryTable({ rows, onDispatch }: Props) {
  const [district, setDistrict] = useState('')
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')

  const districts = useMemo(() => [...new Set(rows.map((r) => r.phc.district))].sort(), [rows])

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return rows.filter(
      (r) =>
        (!district || r.phc.district === district) &&
        (!status || r.item.status === status) &&
        (!needle ||
          r.phc.phc_name.toLowerCase().includes(needle) ||
          r.item.medicine_name.toLowerCase().includes(needle)),
    )
  }, [rows, district, status, q])

  return (
    <div className="card shadow-sm mb-3">
      <div className="card-header bg-white">
        <div className="row g-2 align-items-center">
          <div className="col-12 col-md-auto fw-semibold">Stock telemetry</div>
          <div className="col-6 col-md-auto">
            <select className="form-select form-select-sm" value={district}
                    onChange={(e) => setDistrict(e.target.value)} aria-label="Filter by district">
              <option value="">All districts</option>
              {districts.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          <div className="col-6 col-md-auto">
            <select className="form-select form-select-sm" value={status}
                    onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
              <option value="">All statuses</option>
              <option>CRITICAL</option>
              <option>WARNING</option>
              <option>GREEN</option>
            </select>
          </div>
          <div className="col-12 col-md">
            <input className="form-control form-control-sm" placeholder="Search PHC or medicine"
                   value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
          </div>
          <div className="col-auto text-muted small">{shown.length} of {rows.length} rows</div>
        </div>
      </div>
      <div className="table-responsive">
        <table className="table table-sm table-hover align-middle mb-0">
          <thead className="table-light">
            <tr>
              <th>PHC</th><th>District</th><th>Beds</th><th>Doctors</th><th>Medicine</th>
              <th className="text-end">Stock</th><th className="text-end">7d demand</th>
              <th>Trend</th><th className="text-end">Days left</th><th>Risk</th><th />
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.key} className={r.item.status === 'CRITICAL' ? 'table-danger' : ''}>
                <td>
                  <div className="fw-semibold">{r.phc.phc_name}</div>
                  <div className="text-muted small">{r.phc.state}</div>
                </td>
                <td>{r.phc.district}</td>
                <td>{r.phc.beds_available}/{r.phc.beds_total}</td>
                <td className={r.phc.doctors_present === 0 ? 'text-danger fw-bold' : ''}>
                  {r.phc.doctors_present}/{r.phc.doctors_total}
                </td>
                <td>{r.item.medicine_name}</td>
                <td className="text-end">{r.item.current_stock}</td>
                <td className="text-end">{Math.round(r.item.projected_demand_7d)}</td>
                <td><Sparkline values={r.item.history} /></td>
                <td className="text-end">{formatDays(r.item.days_to_stockout)}</td>
                <td><span className={`badge ${BADGE[r.item.status]}`}>{r.item.status}</span></td>
                <td className="text-end">
                  {r.item.status === 'CRITICAL' &&
                    (r.item.suggested_source_id ? (
                      <button className="btn btn-sm btn-danger" onClick={() => onDispatch(r)}>
                        Dispatch Supply
                      </button>
                    ) : (
                      <span className="text-muted small">No donor</span>
                    ))}
                </td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={11} className="text-center text-muted py-4">No rows match the filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}