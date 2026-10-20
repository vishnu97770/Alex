import { Link as RouterLink } from 'react-router-dom'

// In-app link for the landing page, built on react-router so it shares the app's history.
// `transition` (the original site's "curtain" between landing and app) is accepted and ignored.
// A new screen starts at the top, as it does on a real page load.
export default function Link({ to, transition: _transition = false, onClick, children, ...rest }) {
    const handle = (event) => {
        onClick?.(event)
        if (!event.defaultPrevented && !String(to).includes('#')) window.scrollTo(0, 0)
    }

    return (
        <RouterLink to={to} onClick={handle} {...rest}>
            {children}
        </RouterLink>
    )
}
