import { useEffect, useState } from 'react'

/** Whole seconds since `active` became true; resets to 0 when it turns false. */
export function useElapsed(active: boolean): number {
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    if (!active) return
    const start = Date.now()
    const t = setInterval(() => setSecs(Math.floor((Date.now() - start) / 1000)), 500)
    return () => {
      clearInterval(t)
      setSecs(0)
    }
  }, [active])
  return active ? secs : 0
}

export function progressMessage(secs: number): string {
  if (secs < 3) return 'Reading your description…'
  if (secs < 8) return 'Designing the agent’s role and conversation flow…'
  if (secs < 16) return 'Writing the final brief…'
  return 'The AI model is busy right now. Still working — this can take up to a minute.'
}
