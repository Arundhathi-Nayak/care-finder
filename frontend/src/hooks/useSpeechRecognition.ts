import { useCallback, useEffect, useRef, useState } from 'react'

interface ResultEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}
interface Recognizer {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: ResultEvent) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type Ctor = new () => Recognizer

function getCtor(): Ctor | null {
  const w = window as unknown as { SpeechRecognition?: Ctor; webkitSpeechRecognition?: Ctor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

function messageFor(code: string): string | null {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone is blocked. Allow it in the browser address bar, or type your question.'
    case 'no-speech':
      return 'I did not hear anything. Tap the mic and try again.'
    case 'network':
      return 'Voice input needs an internet connection. Please type your question.'
    case 'aborted':
      return null
    default:
      return `Voice input error (${code}). Please type your question.`
  }
}

/** onFinal receives the full recognised text once the user stops speaking. Nothing is stored. */
export function useSpeechRecognition(onFinal: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)
  const recRef = useRef<Recognizer | null>(null)
  const heardRef = useRef('')
  const onFinalRef = useRef(onFinal)
  const supported = getCtor() !== null

  useEffect(() => {
    onFinalRef.current = onFinal
  })

  // On unmount: detach handlers first so a late onend cannot send a message
  useEffect(
    () => () => {
      const r = recRef.current
      if (r) {
        r.onend = null
        r.onresult = null
        r.onerror = null
        r.stop()
      }
    },
    [],
  )

  const start = useCallback((lang: string) => {
    const C = getCtor()
    if (!C) return
    const rec = new C()
    rec.lang = lang
    rec.interimResults = true
    rec.continuous = false
    heardRef.current = ''
    setInterim('')
    setError(null)

    rec.onresult = (e) => {
      const text = Array.from(e.results).map((r) => r[0].transcript).join(' ')
      heardRef.current = text
      setInterim(text)
    }
    rec.onerror = (e) => setError(messageFor(e.error))
    rec.onend = () => {
      setListening(false)
      setInterim('')
      recRef.current = null
      const text = heardRef.current.trim()
      heardRef.current = ''
      if (text) onFinalRef.current(text)
    }
    recRef.current = rec
    setListening(true)
    try {
      rec.start()
    } catch {
      setListening(false)
      recRef.current = null
    }
  }, [])

  const stop = useCallback(() => recRef.current?.stop(), [])

  return { supported, listening, interim, error, start, stop }
}