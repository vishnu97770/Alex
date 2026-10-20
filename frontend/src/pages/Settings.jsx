import { useState } from 'react'
import { applyTheme, getTheme } from '../lib/theme'

export default function Settings() {
    const [theme, setTheme] = useState(getTheme)
    const toggle = () => {
        const next = theme === 'dark' ? 'light' : 'dark'
        applyTheme(next)
        setTheme(next)
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
            </div>
        </div>
    )
}
