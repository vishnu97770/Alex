import { NavLink, useNavigate } from 'react-router-dom'
import { useListCallsQuery } from '../../api/api'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { callReset } from '../../features/call/slice'
import { transcriptCleared } from '../../features/transcript/slice'
/**
 * The calls bar. Defaults reproduce the original single-user app; MyManager passes its own
 * call list and routes (`calls`, `chatsBase`, `newCallPath`) and hides the legacy Settings link.
 */
export default function Sidebar({
    calls,
    chatsBase = '',
    newCallPath = '/',
    showSettings = true,
    onOpenWhileLive,
    onNewCall,
    activeId,
}) {
    const { data: own } = useListCallsQuery(undefined, { skip: calls !== undefined })
    const data = calls ?? own
    const navigate = useNavigate()
    const dispatch = useAppDispatch()
    const live = useAppSelector((s) => s.call.status)
    const isLive = ['connecting', 'waiting_for_agent', 'connected', 'reconnecting'].includes(live)
    const newCall = () => {
        onNewCall?.()
        if (!['connecting', 'waiting_for_agent', 'connected', 'reconnecting'].includes(live)) {
            dispatch(callReset())
            dispatch(transcriptCleared())
        }
        navigate(newCallPath) // default: always ask for a role first
    }
    return (
        <nav className="sidebar" aria-label="Call history">
            <button className="primary wide" onClick={newCall}>
                + New call
            </button>
            <ul>
                {(data ?? []).map((c) => (
                    <li key={c.id}>
                        <NavLink
                            to={`${chatsBase}/chats/${c.id}`}
                            className={({ isActive }) => ((activeId ? c.id === activeId : isActive) ? 'active' : '')}
                            onClick={(e) => {
                                // on a live call the old call opens beside it, not instead of it
                                if (isLive && onOpenWhileLive) {
                                    e.preventDefault()
                                    onOpenWhileLive(c.id, e.currentTarget)
                                }
                            }}
                        >
                            {c.title ?? 'New call'}
                        </NavLink>
                    </li>
                ))}
            </ul>
            {showSettings && (
                <NavLink to="/settings" className="settings-link">
                    Settings
                </NavLink>
            )}
        </nav>
    )
}
