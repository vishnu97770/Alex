import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
    errorMessage,
    useAuthConfigQuery,
    useLoginMutation,
    useMeQuery,
    useRegisterMutation,
} from '../api/api'

const URL_ERRORS = {
    google_not_configured: 'Google sign-in is not set up on this server yet.',
    google_failed: 'Google sign-in did not complete. Please try again.',
}

export default function CheckinPage() {
    const [params] = useSearchParams()
    const [mode, setMode] = useState(params.get('mode') === 'register' ? 'register' : 'login')
    const [form, setForm] = useState({ username: '', email: '', password: '' })
    const [error, setError] = useState(null)
    const navigate = useNavigate()
    const { currentData: me } = useMeQuery()
    const { data: cfg } = useAuthConfigQuery()
    const [login, { isLoading: loggingIn }] = useLoginMutation()
    const [register, { isLoading: registering }] = useRegisterMutation()
    const busy = loggingIn || registering
    const signup = mode === 'register'

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
    const submit = async (e) => {
        e.preventDefault()
        setError(null)
        try {
            const user = signup
                ? await register({
                      username: form.username,
                      email: form.email,
                      password: form.password,
                  }).unwrap()
                : await login({ email: form.email, password: form.password }).unwrap()
            navigate(`/dashboard/${user.uid}`, { replace: true })
        } catch (err) {
            setError(errorMessage(err, 'Could not sign you in. Please try again.'))
        }
    }
    const shown = error ?? URL_ERRORS[params.get('error')]

    return (
        <div className="center-box-page">
            <form className="box" onSubmit={(e) => void submit(e)} aria-labelledby="checkin-title">
                <h1 id="checkin-title">{signup ? 'Create your account' : 'Sign in'}</h1>
                {me && (
                    <p className="muted signed-in-note">
                        You are already signed in as {me.username}.{' '}
                        <Link to={`/dashboard/${me.uid}`}>Continue to your dashboard</Link>, or use the form
                        to switch accounts.
                    </p>
                )}
                {shown && (
                    <div className="banner error" role="alert">
                        {shown}
                    </div>
                )}
                {signup && (
                    <label>
                        Username
                        <input
                            value={form.username}
                            onChange={set('username')}
                            required
                            minLength={2}
                            maxLength={40}
                        />
                    </label>
                )}
                <label>
                    Email
                    <input
                        type="email"
                        value={form.email}
                        onChange={set('email')}
                        required
                        autoComplete="email"
                    />
                </label>
                <label>
                    Password
                    <input
                        type="password"
                        value={form.password}
                        onChange={set('password')}
                        required
                        minLength={signup ? 8 : 1}
                        maxLength={128}
                        autoComplete={signup ? 'new-password' : 'current-password'}
                    />
                </label>
                <button className="primary wide" disabled={busy}>
                    {busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}
                </button>
                <div className="divider">or</div>
                <a
                    className={`button wide google ${cfg?.google ? '' : 'disabled'}`}
                    href={cfg?.google ? '/api/v1/auth/google/start' : undefined}
                    aria-disabled={!cfg?.google}
                    title={cfg?.google ? undefined : 'Google sign-in is not configured'}
                >
                    Continue with Google
                </a>
                <p className="muted center">
                    {signup ? 'Already have an account?' : 'New here?'}{' '}
                    <button
                        type="button"
                        className="link"
                        onClick={() => setMode(signup ? 'login' : 'register')}
                    >
                        {signup ? 'Sign in' : 'Create an account'}
                    </button>
                </p>
            </form>
        </div>
    )
}
