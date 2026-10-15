import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGenerateProfileMutation, useGetActiveProfileQuery } from '../api/api'
import { useAppSelector } from '../app/hooks'
import { progressMessage, useElapsed } from '../lib/useElapsed'
export default function RolePage() {
    const [text, setText] = useState('')
    const navigate = useNavigate()
    const { data: active } = useGetActiveProfileQuery()
    const [generate] = useGenerateProfileMutation()
    const { generation, error } = useAppSelector((s) => s.agentProfile)
    const pending = generation === 'pending'
    const secs = useElapsed(pending)
    const inflight = useRef(null)
    const submit = async () => {
        try {
            const req = generate({ description: text.trim() })
            inflight.current = req
            await req.unwrap()
            navigate('/call')
        } catch {
            /* error is held in the agentProfile slice and shown below */
        }
    }
    return (
        <div className="role">
            <h1>What should be the role and behaviour of the agent?</h1>
            <textarea
                aria-label="Agent role and behaviour"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="e.g. A friendly receptionist for a dental clinic who books and confirms appointments…"
                rows={7}
                maxLength={6000}
                disabled={pending}
            />
            {error && (
                <div className="banner error" role="alert">
                    {error} <button onClick={() => void submit()}>Retry</button>
                </div>
            )}
            {pending && (
                <div className="banner progress" role="status" aria-live="polite">
                    <span className="spinner" aria-hidden /> {progressMessage(secs)}{' '}
                    <span className="muted">({secs}s)</span>{' '}
                    <button onClick={() => inflight.current?.abort()}>Cancel</button>
                </div>
            )}
            <div className="row">
                <button
                    className="primary"
                    disabled={pending || text.trim().length < 10}
                    onClick={() => void submit()}
                >
                    {pending ? 'Designing your agent…' : 'Continue'}
                </button>
                {active && (
                    <button className="secondary" disabled={pending} onClick={() => navigate('/call')}>
                        Use the role and behaviour from last time
                    </button>
                )}
            </div>
            {active && (
                <p className="muted preview">
                    Last role:{' '}
                    {String(active.structured_fields.role_summary ?? active.context_prompt.slice(0, 160))}
                </p>
            )}
        </div>
    )
}
