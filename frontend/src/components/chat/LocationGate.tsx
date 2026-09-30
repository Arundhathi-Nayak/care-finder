import { useState } from 'react'
import type { GeoStatus } from '../../hooks/useGeolocation'

interface Props {
  status: GeoStatus
  districts: string[]
  onUseLocation: () => void
  onPickDistrict: (d: string) => void
}

export default function LocationGate({ status, districts, onUseLocation, onPickDistrict }: Props) {
  const [manual, setManual] = useState(false)
  const [choice, setChoice] = useState('')
  const failed = status === 'denied' || status === 'unavailable'
  const showDistrict = manual || failed

  return (
    <div className="card shadow-sm">
      <div className="card-body">
        <h1 className="h4">Care Finder</h1>
        <p className="mb-2">
          I help you find nearby government health centres and check medicine availability, beds and
          whether a doctor is present.
        </p>
        <ul className="small text-muted ps-3">
          <li>I am not a doctor and cannot diagnose or advise on treatment.</li>
          <li>In an emergency, call 108 (ambulance) or 112.</li>
          <li>This is demo data, not real facility data.</li>
        </ul>

        <p className="small text-muted mb-2">
          Your location is used only to find nearby facilities and is not stored.
        </p>
        <button className="btn btn-success btn-lg w-100 mb-2" onClick={onUseLocation}
                disabled={status === 'asking'}>
          {status === 'asking' ? 'Waiting for permission…' : '📍 Use my location'}
        </button>

        {failed && (
          <div className="alert alert-warning py-2 small" role="alert">
            {status === 'denied'
              ? 'Location permission was blocked.'
              : 'Could not get your location.'}{' '}
            Please choose your district instead.
          </div>
        )}

        {!showDistrict && (
          <button className="btn btn-link p-0" onClick={() => setManual(true)}>
            Choose a district instead
          </button>
        )}

        {showDistrict && (
          <div className="d-flex gap-2">
            <select className="form-select" value={choice} onChange={(e) => setChoice(e.target.value)}
                    aria-label="District">
              <option value="">Select district…</option>
              {districts.map((d) => <option key={d}>{d}</option>)}
            </select>
            <button className="btn btn-outline-success" disabled={!choice} onClick={() => onPickDistrict(choice)}>
              Continue
            </button>
          </div>
        )}
      </div>
    </div>
  )
}