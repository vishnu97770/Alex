const KEY = 'theme'

// Dark unless the user chose otherwise: it is the landing page's look, and the app matches it.
export const systemTheme = () => 'dark'

export const getTheme = () => {
  try {
    const t = localStorage.getItem(KEY)
    if (t === 'light' || t === 'dark') return t
  } catch {
    /* storage blocked: fall back to the system theme */
  }
  return systemTheme()
}

export const applyTheme = (theme) => {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    /* not persisted, still applied for this session */
  }
}

export const initTheme = () => {
  try {
    const t = localStorage.getItem(KEY)
    if (t === 'light' || t === 'dark') {
      document.documentElement.dataset.theme = t
      return
    }
  } catch {
    /* storage blocked: use the default */
  }
  document.documentElement.dataset.theme = systemTheme()
}
