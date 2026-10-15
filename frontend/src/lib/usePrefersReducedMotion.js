import { useEffect, useState } from 'react'
export function usePrefersReducedMotion() {
  const q = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(() =>
    typeof matchMedia === 'function' ? matchMedia(q).matches : false,
  )
  useEffect(() => {
    if (typeof matchMedia !== 'function') return
    const m = matchMedia(q)
    const h = () => setReduced(m.matches)
    m.addEventListener('change', h)
    return () => m.removeEventListener('change', h)
  }, [])
  return reduced
}
