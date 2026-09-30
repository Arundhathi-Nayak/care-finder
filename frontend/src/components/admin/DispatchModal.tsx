import { useEffect, useRef, useState } from 'react'
import { ApiError, postRedistribution } from '../../api/client'
import type { RedistributionResponse } from '../../types/api'
import type { Row } from './rows'

interface Props {
  row: Row
  onClose: () => void
  onRecorded: () => void   // brief generated and saved: refresh data
  onApproved: () => void   // user confirmed: toast
}

function priorityClass(p: string): string {
  const s = p.toLowerCase()
  if (/(critical|high|urgent|immediate|p1)/.test(s)) return 'text-bg-danger'
  if (/(medium|moderate|p2)/.test(s)) return 'text-bg-warning'
  return 'text-bg-secondary'
}

export default function DispatchModal({ row, onClose, onRecorded, onApproved }: Props) {
  const [res, setRes] = useState<RedistributionResponse | null>(null)
  const [error, setError] = useState<{ msg: string; status: number } | null>(null)
  const started = useRef(false)
  const { item, phc } = row
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (started.current) return          // StrictMode runs effects twice in dev
    started.current = true
    postRedistribution({
      source_phc_id: item.suggested_source_id as string,
      target_phc_id: phc.phc_id,
      item_name: item.medicine_name,
      preview: true,
    })
      .then((r) => setRes(r))
      .catch((e) =>
        setError(e instanceof ApiError ? { msg: e.message, status: e.status } : { msg: 'Request failed', status: 0 }),
      )
  }, [item, phc])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.classList.add('modal-open')
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('modal-open')
    }
  }, [onClose])

  const facts = (res?.facts ?? {}) as Record<string, unknown>
  const distance = typeof facts.distance_km === 'number' ? facts.distance_km : null
  const cross = facts.cross_district === true
  
  async function approve() {
    setSaving(true)
    setError(null)
    try {
      await postRedistribution({
        source_phc_id: item.suggested_source_id as string,
        target_phc_id: phc.phc_id,
        item_name: item.medicine_name,
        preview: false,
      })
      onRecorded()    // refresh table, KPIs and transfers
      onApproved()    // toast and close
    } catch (e) {
      setError(e instanceof ApiError ? { msg: e.message, status: e.status } : { msg: 'Request failed', status: 0 })
    } finally {
      setSaving(false)
    }
  }
  return (
    <>
      <div className="modal d-block" tabIndex={-1} role="dialog" aria-modal="true"
           aria-labelledby="dispatch-title" onClick={onClose}>
        <div className="modal-dialog modal-dialog-centered modal-lg" onClick={(e) => e.stopPropagation()}>
          <div className="modal-content">
            <div className="modal-header">
              <h2 className="modal-title h5" id="dispatch-title">
                Redistribution brief: {item.medicine_name}
              </h2>
              <button type="button" className="btn-close" aria-label="Close" onClick={onClose} />
            </div>

            <div className="modal-body">
              <div className="mb-3">
                <span className="fw-semibold">{item.suggested_source_name ?? item.suggested_source_id}</span>
                <span className="mx-2">→</span>
                <span className="fw-semibold">{phc.phc_name}</span>
                {distance !== null && <span className="text-muted ms-2">({distance.toFixed(1)} km straight line)</span>}
                {cross && <span className="badge text-bg-info ms-2">Cross-district</span>}
              </div>

              {!res && !error && (
                <div className="d-flex align-items-center gap-2 py-4 justify-content-center">
                  <div className="spinner-border spinner-border-sm" role="status" />
                  <span>Generating brief…</span>
                </div>
              )}

              {error && (
                <div className={`alert ${error.status === 409 ? 'alert-warning' : 'alert-danger'} mb-0`} role="alert">
                  {error.msg}
                </div>
              )}

              {res && (
                <>
                  <div className="row g-3 mb-3">
                    <div className="col-6 col-md-3">
                      <div className="text-muted small">Transfer quantity</div>
                      <div className="fs-4 fw-bold">{res.brief.transfer_quantity}</div>
                    </div>
                    <div className="col-6 col-md-3">
                      <div className="text-muted small">Transport mode</div>
                      <div className="fw-semibold">{res.brief.transport_mode}</div>
                    </div>
                    <div className="col-6 col-md-3">
                      <div className="text-muted small">Route priority</div>
                      <span className={`badge ${priorityClass(res.brief.route_priority)}`}>
                        {res.brief.route_priority}
                      </span>
                    </div>
                    <div className="col-6 col-md-3">
                      <div className="text-muted small">Estimated travel time</div>
                      <div className="fw-semibold">{res.brief.estimated_travel_time}</div>
                    </div>
                  </div>
                  <div className="text-muted small">Emergency justification</div>
                  <p className="mb-2">{res.brief.emergency_justification}</p>
                  <span className={`badge ${res.source === 'gemini' ? 'text-bg-success' : 'text-bg-secondary'}`}>
                    Brief by {res.source}
                  </span>
                  {res.fallback_reason && (
                    <span className="text-muted small ms-2">({res.fallback_reason})</span>
                  )}
                </>
              )}
            </div>

            <div className="modal-footer">
              <button className="btn btn-outline-secondary" onClick={onClose}>Close</button>
                {res && (
                <button className="btn btn-success" onClick={() => void approve()} disabled={saving}>
                    {saving ? 'Saving…' : 'Approve & Notify Driver'}
                </button>
                )}
            </div>
          </div>
        </div>
      </div>
      <div className="modal-backdrop show" />
    </>
  )
}