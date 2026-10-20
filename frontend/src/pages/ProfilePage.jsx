import { useRef, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { api, errorMessage, useLogoutMutation, useUploadAvatarMutation } from '../api/api'
import { useAppDispatch } from '../app/hooks'
import ProfileIcon from '../components/Auth/ProfileIcon'

const MAX_BYTES = 2 * 1024 * 1024
const TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']

export default function ProfilePage() {
    const { me } = useOutletContext()
    const navigate = useNavigate()
    const dispatch = useAppDispatch()
    const fileRef = useRef(null)
    const [error, setError] = useState(null)
    const [upload, { isLoading }] = useUploadAvatarMutation()
    const [logout] = useLogoutMutation()

    const onFile = async (e) => {
        const file = e.target.files?.[0]
        e.target.value = ''
        if (!file) return
        setError(null)
        if (!TYPES.includes(file.type)) return setError('Please choose a PNG, JPEG, GIF or WebP image.')
        if (file.size > MAX_BYTES) return setError('The image must be 2 MB or smaller.')
        try {
            await upload({ uid: me.uid, file }).unwrap()
        } catch (err) {
            setError(errorMessage(err, 'Could not upload the picture.'))
        }
    }
    const onLogout = async () => {
        try {
            await logout().unwrap()
        } finally {
            dispatch(api.util.resetApiState())
            navigate('/checkin', { replace: true })
        }
    }

    return (
        <div className="page-column">
            <div className="page-top">
                <h1 className="page-title">My Profile</h1>
            </div>
            <div className="page-body">
                <div className="profile-card">
                    <ProfileIcon user={me} size={112} />
                    <input
                        ref={fileRef}
                        type="file"
                        accept={TYPES.join(',')}
                        hidden
                        aria-label="Upload profile picture"
                        onChange={(e) => void onFile(e)}
                    />
                    <button disabled={isLoading} onClick={() => fileRef.current?.click()}>
                        {isLoading ? 'Uploading…' : 'Upload profile picture'}
                    </button>
                    {error && (
                        <div className="banner error" role="alert">
                            {error}
                        </div>
                    )}
                    <dl className="details">
                        <dt>Username</dt>
                        <dd>{me.username}</dd>
                        <dt>Email</dt>
                        <dd>{me.email}</dd>
                        <dt>Agents</dt>
                        <dd>{me.agent_count}</dd>
                    </dl>
                    <button className="danger" onClick={() => void onLogout()}>
                        Log out
                    </button>
                </div>
            </div>
        </div>
    )
}
