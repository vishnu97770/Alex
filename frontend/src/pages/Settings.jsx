import { useState } from 'react'
import { applyTheme, getTheme } from '../lib/theme'
import {
    applyAccent,
    applyFontFamily,
    applyFontSize,
    DEFAULT_ACCENT,
    FONT_FAMILIES,
    FONT_SIZES,
    getPreferences,
    resetAccent,
} from '../lib/preferences'

const SWATCHES = ['#52ab98', '#4f8cff', '#9b6dff', '#e0609a', '#f0803c', '#d6a516']
const SIZE_LABELS = { small: 'Small', medium: 'Medium', large: 'Large' }

export default function Settings() {
    const [theme, setTheme] = useState(getTheme)
    const [prefs, setPrefs] = useState(getPreferences)
    const toggle = () => {
        const next = theme === 'dark' ? 'light' : 'dark'
        applyTheme(next)
        setTheme(next)
    }
    const setAccent = (hex) => {
        applyAccent(hex)
        setPrefs((p) => ({ ...p, accent: hex.toLowerCase() }))
    }
    return (
        <div className="page-column">
            <div className="page-top">
                <h1 className="page-title">Settings</h1>
            </div>
            <div className="page-body">
                <div className="setting-row">
                    <span id="theme-label">Theme</span>
                    <button
                        role="switch"
                        aria-checked={theme === 'dark'}
                        aria-labelledby="theme-label"
                        onClick={toggle}
                    >
                        {theme === 'dark' ? 'Dark' : 'Light'}
                    </button>
                </div>
                <div className="setting-row">
                    <span id="accent-label">Theme colour</span>
                    <div role="group" aria-labelledby="accent-label" className="swatch-row">
                        {SWATCHES.map((c) => (
                            <button
                                key={c}
                                type="button"
                                className="swatch-button"
                                style={{ background: c }}
                                aria-label={c}
                                aria-pressed={prefs.accent === c}
                                onClick={() => setAccent(c)}
                            />
                        ))}
                        <input
                            type="color"
                            aria-label="Custom colour"
                            value={prefs.accent}
                            onChange={(e) => setAccent(e.target.value)}
                        />
                        <button
                            type="button"
                            disabled={prefs.accent === DEFAULT_ACCENT}
                            onClick={() => {
                                resetAccent()
                                setPrefs((p) => ({ ...p, accent: DEFAULT_ACCENT }))
                            }}
                        >
                            Reset
                        </button>
                    </div>
                </div>
                <div className="setting-row">
                    <span id="size-label">Font size</span>
                    <div role="radiogroup" aria-labelledby="size-label" className="swatch-row">
                        {Object.keys(FONT_SIZES).map((s) => (
                            <button
                                key={s}
                                type="button"
                                role="radio"
                                aria-checked={prefs.fontSize === s}
                                onClick={() => {
                                    applyFontSize(s)
                                    setPrefs((p) => ({ ...p, fontSize: s }))
                                }}
                            >
                                {SIZE_LABELS[s]}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="setting-row">
                    <label id="font-label" htmlFor="font-family">
                        Font
                    </label>
                    <select
                        id="font-family"
                        value={prefs.fontFamily}
                        onChange={(e) => {
                            applyFontFamily(e.target.value)
                            setPrefs((p) => ({ ...p, fontFamily: e.target.value }))
                        }}
                    >
                        {Object.entries(FONT_FAMILIES).map(([k, f]) => (
                            <option key={k} value={k}>
                                {f.label}
                            </option>
                        ))}
                    </select>
                </div>
            </div>
        </div>
    )
}
