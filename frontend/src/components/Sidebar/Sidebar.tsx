import { NavLink, useNavigate } from 'react-router-dom'
import { useListCallsQuery } from '../../api/api'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { callReset } from '../../features/call/slice'
import { transcriptCleared } from '../../features/transcript/slice'

export default function Sidebar() {
  const { data } = useListCallsQuery()
  const navigate = useNavigate()
  const dispatch = useAppDispatch()
  const live = useAppSelector((s) => s.call.status)

  const newCall = () => {
    if (!['connecting', 'waiting_for_agent', 'connected', 'reconnecting'].includes(live)) {
      dispatch(callReset())
      dispatch(transcriptCleared())
    }
    navigate('/') // always ask: define a new role or reuse the last one
  }

  return (
    <nav className="sidebar" aria-label="Call history">
      <button className="primary wide" onClick={newCall}>
        + New call
      </button>
      <ul>
        {(data ?? []).map((c) => (
          <li key={c.id}>
            <NavLink to={`/chats/${c.id}`} className={({ isActive }) => (isActive ? 'active' : '')}>
              {c.title ?? 'New call'}
            </NavLink>
          </li>
        ))}
      </ul>
      <NavLink to="/settings" className="settings-link">
        Settings
      </NavLink>
    </nav>
  )
}
