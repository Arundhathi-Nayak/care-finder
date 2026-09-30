import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { ApiError, getNetworkStatus, postChat } from '../api/client'
import ChatMessage, { type ChatMsg } from '../components/chat/ChatMessage'
import LocationGate from '../components/chat/LocationGate'
import { useGeolocation } from '../hooks/useGeolocation'
import { usePolling } from '../hooks/usePolling'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'
import './CareFinderPage.scss'

const DEFAULT_CHIPS = [
  'Nearest PHC',
  'Is paracetamol available?',
  'Beds near me',
  'Doctors available now',
]

const SPEECH_LANGS = [
  { code: 'en-IN', label: 'English' },
  { code: 'hi-IN', label: 'हिन्दी' },
  { code: 'kn-IN', label: 'ಕನ್ನಡ' },
  { code: 'mr-IN', label: 'मराठी' },
]

export default function CareFinderPage() {
  const geo = useGeolocation()

  const { data } = usePolling(getNetworkStatus, 0)

  const districts = useMemo(
    () => [...new Set((data?.phcs ?? []).map((p) => p.district))].sort(),
    [data],
  )

  const [district, setDistrict] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<{ text: string; retry: string } | null>(null)
  const [speechLang, setSpeechLang] = useState('en-IN')

  const nextId = useRef(1)
  const endRef = useRef<HTMLDivElement>(null)
  const sendRef = useRef<(t: string) => Promise<void>>(async () => {})

  const speech = useSpeechRecognition((t) => void sendRef.current(t))

  const ready = geo.coords !== null || district !== null

  useEffect(() => {
    endRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [messages, loading, error])

  async function send(text: string, retry = false) {
    const t = text.trim()

    if (!t || loading) return

    const base =
      retry && messages.at(-1)?.role === 'user'
        ? messages.slice(0, -1)
        : messages

    const history = base
      .slice(-10)
      .map((m) => ({
        role: m.role,
        text: m.text.slice(0, 2000),
      }))

    if (!retry) {
      setMessages((m) => [
        ...m,
        {
          id: nextId.current++,
          role: 'user',
          text: t,
        },
      ])
    }

    setInput('')
    setError(null)
    setLoading(true)

    try {
      const resp = await postChat({
        message: t.slice(0, 1000),
        history,
        location: geo.coords,
        district_hint: geo.coords ? null : district,
      })

      setMessages((m) => [
        ...m,
        {
          id: nextId.current++,
          role: 'assistant',
          text: resp.reply,
          resp,
        },
      ])
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0

      setError({
        text:
          status === 429
            ? 'Too many requests, please wait a moment and try again.'
            : e instanceof Error
              ? e.message
              : 'Something went wrong.',
        retry: t,
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    sendRef.current = (t) => send(t)
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  function changeLocation() {
    speech.stop()
    geo.reset()
    setDistrict(null)
  }

  if (!ready) {
    return (
      <div className="carefinder-page">
        <div className="carefinder-container">
          <LocationGate
            status={geo.status}
            districts={districts}
            onUseLocation={() => void geo.request()}
            onPickDistrict={setDistrict}
          />
        </div>
      </div>
    )
  }

  const lastAssistant = [...messages]
    .reverse()
    .find((m) => m.role === 'assistant')

  const chips =
    messages.length === 0
      ? DEFAULT_CHIPS
      : lastAssistant?.resp?.suggestions ?? []

  return (
    <div className="carefinder-page">
      <div className="carefinder-container">

        {/* Header */}
        <header className="carefinder-header">
          <div className="brand-section">
            <div className="brand-icon">✚</div>

            <div>
              <h1>CareFinder</h1>
              <p>Your healthcare assistant</p>
            </div>
          </div>

          <div className="location-section">
            <span className="location-badge">
              <span className="location-dot" />
              {geo.coords
                ? 'Using your location'
                : `District: ${district}`}
            </span>

            <button
              type="button"
              className="change-location-btn"
              onClick={changeLocation}
            >
              Change
            </button>
          </div>
        </header>

        {/* Welcome */}
        {messages.length === 0 && (
          <section className="welcome-card">
            <div className="welcome-icon">👋</div>

            <div>
              <h2>How can I help you today?</h2>

              <p>
                Ask about nearby health centres, medicines, beds or doctors.
                You can write or speak in English, हिन्दी, ಕನ್ನಡ or मराठी.
              </p>
            </div>
          </section>
        )}

        {/* Conversation */}
        <main className="conversation-area">
          <div
            className="messages-container"
            role="log"
            aria-live="polite"
            aria-label="Conversation"
          >
            {messages.map((m) => (
              <ChatMessage
                key={m.id}
                msg={m}
                onAsk={(t) => void send(t)}
                busy={loading}
              />
            ))}
          </div>

          {/* Loading */}
          {loading && (
            <div
              className="typing-indicator"
              role="status"
              aria-label="Assistant is typing"
            >
              <div className="assistant-avatar">✚</div>

              <div className="typing-bubble">
                <span />
                <span />
                <span />
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="carefinder-error" role="alert">
              <div className="error-content">
                <span className="error-icon">!</span>
                <span>{error.text}</span>
              </div>

              <button
                type="button"
                className="retry-btn"
                onClick={() => void send(error.retry, true)}
              >
                Retry
              </button>
            </div>
          )}

          {/* Suggestions */}
          {!loading && !speech.listening && chips.length > 0 && (
            <div className="suggestions-section">
              <span className="suggestions-label">
                {messages.length === 0
                  ? 'Try asking'
                  : 'You might also ask'}
              </span>

              <div className="suggestion-chips">
                {chips.map((c) => (
                  <button
                    type="button"
                    key={c}
                    className="suggestion-chip"
                    onClick={() => void send(c)}
                  >
                    <span>{c}</span>
                    <span className="chip-arrow">→</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div ref={endRef} />
        </main>

        {/* Chat input */}
        <div className="composer-wrapper">
          <form onSubmit={onSubmit} className="composer">

            {speech.error && (
              <div
                className="speech-error"
                role="alert"
              >
                {speech.error}
              </div>
            )}

            <div className="composer-main">
              <div className="input-wrapper">
                <input
                  className="carefinder-input"
                  value={
                    speech.listening
                      ? speech.interim
                      : input
                  }
                  readOnly={speech.listening}
                  maxLength={1000}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={
                    speech.listening
                      ? 'Listening…'
                      : 'Type your question…'
                  }
                  aria-label="Your message"
                  disabled={loading}
                />

                {speech.listening && (
                  <div className="listening-indicator">
                    <span />
                    Listening
                  </div>
                )}
              </div>

              {speech.supported && (
                <button
                  type="button"
                  className={`voice-btn ${
                    speech.listening ? 'voice-active' : ''
                  }`}
                  onClick={() =>
                    speech.listening
                      ? speech.stop()
                      : speech.start(speechLang)
                  }
                  disabled={loading}
                  aria-pressed={speech.listening}
                  aria-label={
                    speech.listening
                      ? 'Stop listening'
                      : 'Speak your question'
                  }
                >
                  {speech.listening ? '■' : '🎤'}
                </button>
              )}

              <button
                className="send-btn"
                type="submit"
                disabled={
                  loading ||
                  speech.listening ||
                  !input.trim()
                }
                aria-label="Send message"
              >
                <span>Send</span>
                <span className="send-arrow">→</span>
              </button>
            </div>

            {speech.supported && (
              <div className="language-selector">
                <span>🎙️</span>

                <label htmlFor="speech-lang">
                  Speak in
                </label>

                <select
                  id="speech-lang"
                  value={speechLang}
                  onChange={(e) => setSpeechLang(e.target.value)}
                  disabled={speech.listening}
                >
                  {SPEECH_LANGS.map((l) => (
                    <option
                      key={l.code}
                      value={l.code}
                    >
                      {l.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </form>

          <p className="privacy-note">
            CareFinder helps you find nearby healthcare services.
          </p>
        </div>

      </div>
    </div>
  )
}