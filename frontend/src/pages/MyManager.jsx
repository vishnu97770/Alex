import { Outlet, useOutletContext } from 'react-router-dom'
import { useListManagerCallsQuery } from '../api/api'
import Sidebar from '../components/Sidebar/Sidebar'
import { CallProvider } from '../features/call/CallProvider'

/**
 * Same design as the original chat page: calls bar on the left, chat + moving sphere in the middle
 * (live call at `/manager/:uid`, a past call at `/manager/:uid/chats/:id`), summary panel on the right.
 * The shared main navbar is supplied by AppLayout.
 */
export default function MyManager() {
    const { me } = useOutletContext()
    const { data: calls } = useListManagerCallsQuery(me.uid)
    const base = `/manager/${me.uid}`
    return (
        <CallProvider managerUid={me.uid}>
            <div className="manager-layout">
                <Sidebar calls={calls ?? []} chatsBase={base} newCallPath={base} showSettings={false} />
                <main>
                    <Outlet />
                </main>
            </div>
        </CallProvider>
    )
}
