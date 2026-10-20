import { Outlet, useOutletContext } from 'react-router-dom'
import Navbar from '../Navbar/Navbar'

/** Left: the vertical navbar. Right: the page. Every main page is rendered inside this layout. */
export default function AppLayout() {
    const ctx = useOutletContext()
    return (
        <div className="app-layout">
            <Navbar uid={ctx.me.uid} />
            <div className="app-content">
                <Outlet context={ctx} />
            </div>
        </div>
    )
}
