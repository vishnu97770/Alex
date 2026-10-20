// Appearance preferences besides light/dark (see theme.js). Stored per browser, like the theme.
const KEYS = { accent: 'accent', fontSize: 'fontSize', fontFamily: 'fontFamily' }

export const DEFAULT_ACCENT = '#52ab98' // --brand in tokens.css

// Sizes are our own choice (Claude.ai's exact values are not documented): root font size in px.
export const FONT_SIZES = { small: 14, medium: 16, large: 18 }
const SYSTEM_STACK =
  'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
export const FONT_FAMILIES = {
  default: { label: 'Geist (default)', stack: null }, // keeps the stack from tokens.css
  'open-sans': { label: 'Open Sans', stack: `"Open Sans Variable", ${SYSTEM_STACK}` },
  system: { label: 'System', stack: SYSTEM_STACK },
}

const read = (k) => {
  try {
    return localStorage.getItem(k)
  } catch {
    return null
  }
}
const write = (k, v) => {
  try {
    if (v === null) localStorage.removeItem(k)
    else localStorage.setItem(k, v)
  } catch {
    /* not persisted, still applied for this session */
  }
}

export const isHex = (v) => typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v)

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
const toHex = (c) => `#${c.map((n) => Math.round(n).toString(16).padStart(2, '0')).join('')}`
const mix = (c, to, t) => c.map((n, i) => n + (to[i] - n) * t)
// WCAG relative luminance, used to pick readable text on the accent.
const luminance = (c) => {
  const [r, g, b] = c.map((n) => {
    const s = n / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** The tokens derived from one accent colour: light variant for dark surfaces, dark one for light surfaces. */
export const accentTokens = (hex) => {
  const c = rgb(hex)
  return {
    '--brand': hex.toLowerCase(),
    '--brand-hi': toHex(mix(c, [255, 255, 255], 0.4)),
    '--brand-lo': toHex(mix(c, [0, 0, 0], 0.45)),
    '--brand-rgb': c.join(', '),
    '--on-accent': luminance(c) > 0.35 ? '#03110d' : '#ffffff',
  }
}

export const getPreferences = () => {
  const accent = read(KEYS.accent)
  const size = read(KEYS.fontSize)
  const family = read(KEYS.fontFamily)
  return {
    accent: isHex(accent) ? accent.toLowerCase() : DEFAULT_ACCENT,
    fontSize: size in FONT_SIZES ? size : 'medium',
    fontFamily: family in FONT_FAMILIES ? family : 'default',
  }
}

const root = () => document.documentElement

export const applyAccent = (hex) => {
  const tokens = accentTokens(hex)
  for (const [k, v] of Object.entries(tokens)) root().style.setProperty(k, v)
  write(KEYS.accent, hex.toLowerCase() === DEFAULT_ACCENT ? null : hex.toLowerCase())
}
export const resetAccent = () => {
  for (const k of Object.keys(accentTokens(DEFAULT_ACCENT))) root().style.removeProperty(k)
  write(KEYS.accent, null)
}
export const applyFontSize = (size) => {
  root().style.fontSize = `${FONT_SIZES[size]}px`
  write(KEYS.fontSize, size === 'medium' ? null : size)
}
export const applyFontFamily = (family) => {
  const { stack } = FONT_FAMILIES[family]
  if (stack) root().style.setProperty('--font-sans', stack)
  else root().style.removeProperty('--font-sans')
  write(KEYS.fontFamily, family === 'default' ? null : family)
}

export const initPreferences = () => {
  const p = getPreferences()
  if (p.accent !== DEFAULT_ACCENT) applyAccent(p.accent)
  applyFontSize(p.fontSize)
  applyFontFamily(p.fontFamily)
}
