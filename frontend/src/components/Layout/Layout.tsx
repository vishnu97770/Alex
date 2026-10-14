import { Outlet } from 'react-router-dom'
import { CallProvider } from '../../features/call/CallProvider'
import Sidebar from '../Sidebar/Sidebar'

export default function Layout() {
  return (
    <CallProvider>
      <div className="shell">
        <Sidebar />
        <main>
          <Outlet />
        </main>
      </div>
    </CallProvider>
  )
}
