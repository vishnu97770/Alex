import { NavLink } from 'react-router-dom'

export const NAV_ITEMS = [
    { label: 'My Dashboard', path: 'dashboard' },
    { label: 'My Agents', path: 'agents' },
    { label: 'My Manager', path: 'manager' },
    { label: 'My Profile', path: 'profile' },
    { label: 'Settings', path: 'settings' },
]

/** The one vertical navbar shared by Dashboard, MyAgents, MyManager, ProfilePage and Settings. */
export default function Navbar({ uid }) {
    return (
        <nav className="navbar" aria-label="Main">
            {NAV_ITEMS.map((i) => (
                <NavLink
                    key={i.path}
                    to={`/${i.path}/${uid}`}
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                    {i.label}
                </NavLink>
            ))}
        </nav>
    )
}
