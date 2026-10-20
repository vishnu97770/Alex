import {
  accentTokens,
  applyAccent,
  applyFontFamily,
  applyFontSize,
  DEFAULT_ACCENT,
  getPreferences,
  isHex,
  resetAccent,
} from './preferences'

afterEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('style')
})

it('derives the accent family from one colour and picks readable text', () => {
  const t = accentTokens('#000000')
  expect(t['--brand']).toBe('#000000')
  expect(t['--brand-rgb']).toBe('0, 0, 0')
  expect(t['--on-accent']).toBe('#ffffff')
  expect(accentTokens('#ffffff')['--on-accent']).toBe('#03110d')
  expect(accentTokens('#808080')['--brand-hi']).not.toBe(accentTokens('#808080')['--brand-lo'])
})

it('applies, persists and resets the accent', () => {
  applyAccent('#4f8cff')
  expect(document.documentElement.style.getPropertyValue('--brand')).toBe('#4f8cff')
  expect(getPreferences().accent).toBe('#4f8cff')
  resetAccent()
  expect(document.documentElement.style.getPropertyValue('--brand')).toBe('')
  expect(getPreferences().accent).toBe(DEFAULT_ACCENT)
})

it('applies font size and family, and ignores junk in storage', () => {
  applyFontSize('large')
  expect(document.documentElement.style.fontSize).toBe('18px')
  applyFontFamily('system')
  expect(document.documentElement.style.getPropertyValue('--font-sans')).toContain('system-ui')
  applyFontFamily('default')
  expect(document.documentElement.style.getPropertyValue('--font-sans')).toBe('')
  localStorage.setItem('accent', 'red; background:url(x)')
  localStorage.setItem('fontSize', 'huge')
  localStorage.setItem('fontFamily', 'comic')
  expect(getPreferences()).toEqual({ accent: DEFAULT_ACCENT, fontSize: 'medium', fontFamily: 'default' })
  expect(isHex('#12abEF')).toBe(true)
  expect(isHex('#12abE')).toBe(false)
})
