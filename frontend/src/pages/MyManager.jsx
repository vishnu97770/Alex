import { useCallback, useEffect, useRef, useState } from 'react'
import { Outlet, useOutletContext } from 'react-router-dom'
import { useListManagerCallsQuery } from '../api/api'
import { useAppSelector } from '../app/hooks'
import PastCall from '../components/PastCall/PastCall'
import Sidebar from '../components/Sidebar/Sidebar'
import { CallProvider, useCall } from '../features/call/CallProvider'
import CallPage from './CallPage'

const LIVE = ['connecting', 'waiting_for_agent', 'connected', 'reconnecting']

/** The two-option menu that appears next to an old call clicked during a live call. */
function ViewPicker({ anchor, onPick, onDismiss }) {
    const ref = useRef(null)
    useEffect(() => {
        ref.current?.querySelector('button')?.focus()
        const onKey = (e) => e.key === 'Escape' && onDismiss()
        const onDown = (e) => !ref.current?.contains(e.target) && onDismiss()
        document.addEventListener('keydown', onKey)
        document.addEventListener('mousedown', onDown)
        return () => {
            document.removeEventListener('keydown', onKey)
            document.removeEventListener('mousedown', onDown)
        }
    }, [onDismiss])
    const r = anchor.getBoundingClientRect()
    return (
        <div
            ref={ref}
            className="view-picker"
            role="menu"
            aria-label="How do you want to open this call?"
            style={{ top: r.top + r.height / 2, left: r.right + 8 }}
        >
            <button role="menuitem" type="button" onClick={() => onPick('full')}>
                Full view
            </button>
            <button role="menuitem" type="button" onClick={() => onPick('split')}>
                Split view
            </button>
        </div>
    )
}

/**
 * Lives inside CallProvider, so the LiveKit room is untouched by anything that happens here.
 * `open` is an old call shown while a live call keeps running: { id, mode: 'split' | 'full' }.
 */
function ManagerBody({ base, calls }) {
    const status = useAppSelector((s) => s.call.status)
    const muted = useAppSelector((s) => s.call.muted)
    const { setMuted } = useCall()
    const live = LIVE.includes(status)
    const [open, setOpen] = useState(null)
    const [picker, setPicker] = useState(null) // { id, anchor }
    const autoMuted = useRef(false)
    const mutedRef = useRef(muted)
    mutedRef.current = muted
    const mode = live ? (open?.mode ?? null) : null

    // The call ended while an old call was open: back to the normal layout (the summary opens there).
    useEffect(() => {
        if (!live) {
            setOpen(null)
            setPicker(null)
            autoMuted.current = false
        }
    }, [live])

    // Full view: the call carries on in the background with the microphone off, restored afterwards.
    useEffect(() => {
        if (mode !== 'full') return undefined
        if (!mutedRef.current) {
            autoMuted.current = true
            void setMuted(true)
        }
        return () => {
            if (autoMuted.current) {
                autoMuted.current = false
                void setMuted(false)
            }
        }
    }, [mode, setMuted])

    const onOpenWhileLive = useCallback(
        (id, anchor) => {
            if (open) {
                if (id !== open.id) setOpen({ ...open, id }) // replaces it, same place, same mode
                return
            }
            setPicker({ id, anchor })
        },
        [open],
    )
    const dismiss = useCallback(() => setPicker(null), [])
    const close = useCallback(() => setOpen(null), [])
    const pick = (m) => {
        setOpen({ id: picker.id, mode: m })
        setPicker(null)
    }

    let main = <Outlet />
    if (mode === 'split') {
        main = (
            <div className="manager-split">
                <div className="manager-split-pane">
                    <CallPage />
                </div>
                <div className="manager-split-pane">
                    <PastCall id={open.id} compact onClose={close} />
                </div>
            </div>
        )
    } else if (mode === 'full') {
        main = (
            <>
                <div className="live-banner" role="status">
                    <span>Your call is still running with the microphone off.</span>
                    <button type="button" className="primary" onClick={close}>
                        Back to call
                    </button>
                </div>
                <PastCall id={open.id} onClose={close} />
            </>
        )
    }
    return (
        <div className="manager-layout">
            <Sidebar
                calls={calls}
                chatsBase={base}
                newCallPath={base}
                showSettings={false}
                onOpenWhileLive={onOpenWhileLive}
                onNewCall={close}
                activeId={mode ? open.id : undefined}
            />
            <main>{main}</main>
            {picker && <ViewPicker anchor={picker.anchor} onPick={pick} onDismiss={dismiss} />}
        </div>
    )
}

/**
 * Same design as the original chat page: calls bar on the left, chat + moving sphere in the middle
 * (live call at `/manager/:uid`, a past call at `/manager/:uid/chats/:id`), summary panel on the right.
 * During a live call an old call opens in a full or split view without ending the call.
 * The shared main navbar is supplied by AppLayout.
 */
export default function MyManager() {
    const { me } = useOutletContext()
    const { data: calls } = useListManagerCallsQuery(me.uid)
    return (
        <CallProvider managerUid={me.uid}>
            <ManagerBody base={`/manager/${me.uid}`} calls={calls ?? []} />
        </CallProvider>
    )
}
