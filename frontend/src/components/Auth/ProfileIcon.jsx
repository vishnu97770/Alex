export default function ProfileIcon({ user, size = 40 }) {
    if (user.avatar_url)
        return (
            <img
                className="avatar"
                src={user.avatar_url}
                alt={`${user.username}'s profile picture`}
                width={size}
                height={size}
            />
        )
    return (
        <span className="avatar placeholder" style={{ width: size, height: size }} aria-hidden>
            <svg viewBox="0 0 24 24" width={size * 0.6} height={size * 0.6} fill="currentColor">
                <circle cx="12" cy="8" r="4" />
                <path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z" />
            </svg>
        </span>
    )
}
