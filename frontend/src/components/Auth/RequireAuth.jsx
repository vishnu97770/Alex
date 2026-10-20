import { Navigate, Outlet, useParams } from 'react-router-dom'
import { useMeQuery } from '../../api/api'
import { useScreenTimeHeartbeat } from '../../lib/useScreenTimeHeartbeat'

/** Frontend guard; the backend remains the source of truth (every API call re-checks the token). */
export default function RequireAuth() {
    const { uid } = useParams()
    const { currentData: me, isLoading, isError } = useMeQuery()
    useScreenTimeHeartbeat(me?.uid) // no-op until signed in; covers every protected page
    if (isLoading) return <p className="muted center page-loading">Loading…</p>
    if (isError || !me) return <Navigate to="/checkin" replace />
    if (uid && uid !== me.uid) return <Navigate to={`/dashboard/${me.uid}`} replace />
    return <Outlet context={{ me }} />
}
