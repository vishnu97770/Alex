import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import AgentGraphBox from './AgentGraphBox'

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

/**
 * Read-only version of the update page plus the agent's own graph, shown over a blurred backdrop.
 * Closes with the button, Escape or a click on the backdrop; focus is kept inside and restored on close.
 */
export default function AgentInfo({ uid, agent, colorIndex, onClose }) {
    const dialogRef = useRef(null)
    const closeRef = useRef(null)
    useEffect(() => {
        const opener = document.activeElement
        const overflow = document.body.style.overflow
        document.body.style.overflow = 'hidden'
        closeRef.current?.focus()
        const onKey = (e) => {
            if (e.key === 'Escape') return onClose()
            if (e.key !== 'Tab') return
            const items = dialogRef.current?.querySelectorAll(FOCUSABLE)
            if (!items?.length) return
            const first = items[0]
            const last = items[items.length - 1]
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault()
                last.focus()
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault()
                first.focus()
            }
        }
        document.addEventListener('keydown', onKey)
        return () => {
            document.removeEventListener('keydown', onKey)
            document.body.style.overflow = overflow
            if (opener instanceof HTMLElement) opener.focus()
        }
    }, [onClose])

    return createPortal(
        <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
            <div
                ref={dialogRef}
                className="box wide-box agent-info"
                role="dialog"
                aria-modal="true"
                aria-labelledby="agent-info-title"
                style={{ display: 'flex', flexDirection: 'column' }}
            >
                <section className="agent-info-details">
                    <div className="agent-info-head">
                        <h1 id="agent-info-title">Agent info</h1>
                        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close">
                            Close
                        </button>
                    </div>
                    <div className="field">
                        <span className="field-label">Agent name</span>
                        <div className="readonly-field">{agent.name}</div>
                    </div>
                    <div className="field">
                        <span className="field-label">Role and behaviour of the agent</span>
                        <div className="readonly-field readonly-multiline">{agent.role_behavior}</div>
                    </div>
                </section>
                <section className="agent-info-graph" aria-label={`${agent.name} usage`}>
                    <AgentGraphBox uid={uid} agentId={agent.aid} colorIndex={colorIndex} />
                </section>
            </div>
        </div>,
        document.body,
    )
}
