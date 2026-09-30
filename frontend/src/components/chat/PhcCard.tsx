import type { Availability, PhcCard as Card } from '../../types/api'

interface Props {
  card: Card
  onAsk: (text: string) => void
  disabled?: boolean
}

const CHIP: Record<Availability, string> = {
  IN_STOCK: 'text-bg-success',
  LOW: 'text-bg-warning',
  OUT: 'text-bg-danger',
}
const LABEL: Record<Availability, string> = { IN_STOCK: 'In stock', LOW: 'Low', OUT: 'Out' }

function bedsClass(avail: number, total: number): string {
  if (avail <= 0) return 'text-bg-danger'
  if (total > 0 && avail / total <= 0.25) return 'text-bg-warning'
  return 'text-bg-success'
}

export default function PhcCard({ card, onAsk, disabled }: Props) {
  return (
    <div className="card shadow-sm mb-2">
      <div className="card-body p-3">
        <div className="d-flex justify-content-between align-items-start gap-2">
          <div>
            <div className="fw-bold">{card.name}</div>
            <div className="text-muted small">{card.district}</div>
          </div>
          {card.distance_km !== null && (
            <span className="badge text-bg-primary fs-6">{card.distance_km} km</span>
          )}
        </div>

        <div className="d-flex flex-wrap gap-2 my-2">
          <span className={`badge ${bedsClass(card.beds_available, card.beds_total)}`}>
            Beds {card.beds_available}/{card.beds_total}
          </span>
          {card.doctors_present === 0 ? (
            <span className="badge text-bg-danger">No doctor present</span>
          ) : (
            <span className="badge text-bg-success">
              Doctors {card.doctors_present}/{card.doctors_total}
            </span>
          )}
        </div>

        {card.medicines.length > 0 && (
          <div className="d-flex flex-wrap gap-1 mb-2">
            {card.medicines.map((m) => (
              <span key={m.name} className={`badge ${CHIP[m.availability]}`}>
                {m.name}: {LABEL[m.availability]}
              </span>
            ))}
          </div>
        )}

        <div className="d-flex flex-wrap gap-2">
          <a className="btn btn-success btn-sm py-2 px-3" href={card.maps_url} target="_blank"
             rel="noopener noreferrer" aria-label={`Get directions to ${card.name}`}>
            Get directions
          </a>
          <button className="btn btn-outline-secondary btn-sm py-2 px-3" disabled={disabled}
                  onClick={() => onAsk(`Tell me about ${card.name}`)}
                  aria-label={`Ask about ${card.name}`}>
            Ask about this PHC
          </button>
        </div>
      </div>
    </div>
  )
}