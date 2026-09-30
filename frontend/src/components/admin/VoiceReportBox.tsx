import { useEffect, useRef, useState } from 'react'
import { ApiError, postVoiceReport } from '../../api/client'
import type { PhcRow, VoiceReportResponse } from '../../types/api'

interface Props {
  phcs: PhcRow[]
  onApplied: () => void
}

// Minimal Web Speech typings (not in every TS lib version)
interface SpeechResultEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}
interface Recognizer {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: SpeechResultEvent) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type RecognizerCtor = new () => Recognizer

const getRecognizerCtor = (): RecognizerCtor | null => {
  const w = window as unknown as { SpeechRecognition?: RecognizerCtor; webkitSpeechRecognition?: RecognizerCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

const LANGS = [
  { code: 'hi-IN', label: 'Hindi' },
  { code: 'kn-IN', label: 'Kannada' },
  { code: 'mr-IN', label: 'Marathi' },
  { code: 'en-IN', label: 'English' },
]

const SAMPLES = {
  hi: { lang: 'hi-IN', text: 'आज 85 मरीज आए, पैरासिटामोल का स्टॉक 60 बचा है, डॉक्टर आज उपस्थित हैं।' },
  kn: { lang: 'kn-IN', text: 'ಇಂದು 70 ರೋಗಿಗಳು ಬಂದಿದ್ದಾರೆ, ಪ್ಯಾರಸಿಟಮಾಲ್ ಸ್ಟಾಕ್ 50 ಇದೆ, ವೈದ್ಯರು ಇಲ್ಲ.' },
}

function summarize(r: VoiceReportResponse): string[] {
  const x = r.extracted
  const out: string[] = []
  if (x.patient_count !== null) out.push(`Today's footfall recorded: ${x.patient_count} patients`)
  if (x.paracetamol_stock !== null) out.push(`Paracetamol stock set to ${x.paracetamol_stock}`)
  if (x.doctor_present !== null) out.push(x.doctor_present ? 'Doctor marked present' : 'Doctor marked absent')
  if (x.emergency_notes) out.push(`Notes: ${x.emergency_notes}`)
  if (out.length === 0) out.push('Nothing could be extracted from this transcript.')
  return out
}

export default function VoiceReportBox({ phcs, onApplied }: Props) {
  const [phcId, setPhcId] = useState('')
  const [language, setLanguage] = useState('hi-IN')
  const [transcript, setTranscript] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const [result, setResult] = useState<VoiceReportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recRef = useRef<Recognizer | null>(null)
  const heardRef = useRef('')
  const phcRef = useRef(phcId)
  const langRef = useRef(language)
  const supported = getRecognizerCtor() !== null

  useEffect(() => { phcRef.current = phcId }, [phcId])
  useEffect(() => { langRef.current = language }, [language])
  useEffect(() => {
    if (!phcId && phcs.length) setPhcId(phcs[0].phc_id)
  }, [phcs, phcId])
  useEffect(() => () => recRef.current?.stop(), [])

  async function submit(text: string) {
    const t = text.trim()
    if (!t || !phcRef.current) return
    setBusy(true)
    setError(null)
    try {
      const r = await postVoiceReport({
        audio_transcript: t, phc_id: phcRef.current, language: langRef.current,
      })
      setResult(r)
      onApplied()
    } catch (e) {
      setResult(null)
      setError(e instanceof ApiError ? e.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  function toggleMic() {
    if (listening) {
      recRef.current?.stop()
      return
    }
    const Ctor = getRecognizerCtor()
    if (!Ctor) return
    const rec = new Ctor()
    rec.lang = langRef.current
    rec.interimResults = true
    rec.continuous = false
    heardRef.current = ''
    rec.onresult = (e) => {
      const text = Array.from(e.results).map((r) => r[0].transcript).join(' ')
      heardRef.current = text
      setTranscript(text)
    }
    rec.onerror = (e) => {
      setError(
        e.error === 'not-allowed' || e.error === 'service-not-allowed'
          ? 'Microphone permission was blocked. Allow it in the browser address bar, or type the report.'
          : e.error === 'no-speech'
            ? 'No speech detected. Try again.'
            : `Speech recognition error: ${e.error}`,
      )
    }
    rec.onend = () => {
      setListening(false)
      recRef.current = null
      if (heardRef.current.trim()) void submit(heardRef.current)   // auto-submit
    }
    recRef.current = rec
    setError(null)
    setListening(true)
    try {
      rec.start()
    } catch {
      setListening(false)
    }
  }

  function loadSample(key: 'hi' | 'kn') {
    setLanguage(SAMPLES[key].lang)
    setTranscript(SAMPLES[key].text)
    setResult(null)
    setError(null)
  }

  return (
    <div className="card shadow-sm h-100">
      <div className="card-header bg-white fw-semibold">Voice / text daily report</div>
      <div className="card-body">
        <div className="row g-2 mb-2">
          <div className="col-7">
            <label className="form-label small mb-1" htmlFor="vr-phc">PHC</label>
            <select id="vr-phc" className="form-select form-select-sm" value={phcId}
                    onChange={(e) => setPhcId(e.target.value)}>
              {phcs.map((p) => <option key={p.phc_id} value={p.phc_id}>{p.phc_name} ({p.district})</option>)}
            </select>
          </div>
          <div className="col-5">
            <label className="form-label small mb-1" htmlFor="vr-lang">Language</label>
            <select id="vr-lang" className="form-select form-select-sm" value={language}
                    onChange={(e) => setLanguage(e.target.value)} disabled={listening}>
              {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label} ({l.code})</option>)}
            </select>
          </div>
        </div>

        <textarea className="form-control mb-2" rows={4} value={transcript}
                  placeholder="Speak or type the daily report, e.g. patients today, paracetamol stock, doctor present?"
                  onChange={(e) => setTranscript(e.target.value)} aria-label="Report transcript" />

        <div className="d-flex flex-wrap gap-2 mb-2">
          <button className="btn btn-success btn-sm" disabled={busy || !transcript.trim() || !phcId}
                  onClick={() => void submit(transcript)}>
            {busy ? 'Extracting…' : 'Extract Data via Gemini AI'}
          </button>
          <button className="btn btn-outline-secondary btn-sm" onClick={() => loadSample('hi')}>Hindi sample</button>
          <button className="btn btn-outline-secondary btn-sm" onClick={() => loadSample('kn')}>Kannada sample</button>
          {supported && (
            <button className={`btn btn-sm ${listening ? 'btn-danger' : 'btn-outline-primary'}`}
                    onClick={toggleMic} aria-pressed={listening}>
              {listening ? '● Listening… tap to stop' : '🎤 Speak'}
            </button>
          )}
        </div>
        {!supported && (
          <div className="text-muted small mb-2">Voice input needs Chrome or Edge. You can still type or use the samples.</div>
        )}

        {error && <div className="alert alert-danger py-2 small" role="alert">{error}</div>}

        {result && (
          <>
            <div className="alert alert-success py-2 small mb-2" role="status">
              <div className="fw-semibold mb-1">
                Applied to network <span className="badge text-bg-light ms-1">{result.source}</span>
              </div>
              <ul className="mb-0 ps-3">{summarize(result).map((s) => <li key={s}>{s}</li>)}</ul>
              {result.fallback_reason && <div className="text-muted mt-1">({result.fallback_reason})</div>}
            </div>
            <pre className="bg-dark text-light rounded p-2 small mb-0" style={{ maxHeight: 220, overflow: 'auto' }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </>
        )}
      </div>
    </div>
  )
}