import { useEffect } from 'react'
import { api } from '../api/api'
import { useAppDispatch } from '../app/hooks'

export const BEAT_MS = 30_000
const MIN_FLUSH_S = 5
const MAX_S = 60 // the server caps a heartbeat at the same value

/**
 * Reports foreground time while signed in: a beat every 30 s, only while the tab is visible, plus a
 * flush of the remainder when the tab is hidden. It sends seconds of use only, never what was viewed.
 */
export function useScreenTimeHeartbeat(uid) {
  const dispatch = useAppDispatch()
  useEffect(() => {
    if (!uid) return undefined
    let since = document.visibilityState === 'visible' ? Date.now() : null
    const flush = (min) => {
      if (since === null) return
      const seconds = Math.min(MAX_S, Math.round((Date.now() - since) / 1000))
      if (seconds < min) return
      since = Date.now()
      void dispatch(api.endpoints.sendHeartbeat.initiate({ uid, seconds }))
    }
    const timer = setInterval(() => flush(1), BEAT_MS)
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') {
        flush(MIN_FLUSH_S)
        since = null
      } else {
        since = Date.now()
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
      flush(MIN_FLUSH_S)
    }
  }, [uid, dispatch])
}
