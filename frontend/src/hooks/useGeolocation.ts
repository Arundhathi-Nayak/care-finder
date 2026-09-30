import { useCallback, useState } from 'react'

export type GeoStatus = 'idle' | 'asking' | 'granted' | 'denied' | 'unavailable'
export interface Coords { lat: number; lng: number }

/** Coordinates live only in React state: never written to storage or logged. */
export function useGeolocation() {
  const [status, setStatus] = useState<GeoStatus>('idle')
  const [coords, setCoords] = useState<Coords | null>(null)

  const request = useCallback((): Promise<Coords | null> => {
    if (!('geolocation' in navigator)) {
      setStatus('unavailable')
      return Promise.resolve(null)
    }
    setStatus('asking')
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const c = { lat: pos.coords.latitude, lng: pos.coords.longitude }
          setCoords(c)
          setStatus('granted')
          resolve(c)
        },
        (err) => {
          setStatus(err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable')
          resolve(null)
        },
        { timeout: 10_000, maximumAge: 60_000, enableHighAccuracy: false },
      )
    })
  }, [])

  const reset = useCallback(() => {
    setCoords(null)
    setStatus('idle')
  }, [])

  return { status, coords, request, reset }
}