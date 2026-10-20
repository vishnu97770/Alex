import { useEffect, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { errorMessage, useGetAgentQuery, useUpdateAgentMutation } from '../api/api'

export default function AgentUpdater() {
    const { me } = useOutletContext()
    const { aid } = useParams()
    const navigate = useNavigate()
    const { data: agent, isLoading, isError } = useGetAgentQuery({ uid: me.uid, aid })
    const [update, { isLoading: saving }] = useUpdateAgentMutation()
    const [name, setName] = useState('')
    const [role, setRole] = useState('')
    const [error, setError] = useState(null)
    useEffect(() => {
        if (agent) {
            setName(agent.name)
            setRole(agent.role_behavior)
        }
    }, [agent?.aid]) // eslint-disable-line react-hooks/exhaustive-deps

    if (isLoading) return <p className="muted center page-loading">Loading…</p>
    if (isError || !agent || agent.lifecycle !== 'ACTIVE')
        return <p className="muted center page-loading">Agent not found.</p>

    const submit = async (e) => {
        e.preventDefault()
        setError(null)
        try {
            await update({ uid: me.uid, aid, name: name.trim(), role_behavior: role.trim() }).unwrap()
            navigate(`/agents/${me.uid}`)
        } catch (err) {
            setError(errorMessage(err))
        }
    }
    return (
        <div className="center-box-page">
            <form className="box wide-box" onSubmit={(e) => void submit(e)}>
                <h1>Update agent</h1>
                {error && (
                    <div className="banner error" role="alert">
                        {error}
                    </div>
                )}
                <label>
                    Update Agent name
                    <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
                </label>
                <label>
                    Update role and behaviour of the agent
                    <textarea
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                        required
                        minLength={10}
                        maxLength={6000}
                        rows={7}
                    />
                </label>
                <div className="box-actions">
                    <button type="button" onClick={() => navigate(`/agents/${me.uid}`)}>
                        Cancel
                    </button>
                    <button
                        className="primary"
                        disabled={saving || name.trim() === '' || role.trim().length < 10}
                    >
                        {saving ? 'Saving…' : 'Save changes'}
                    </button>
                </div>
            </form>
        </div>
    )
}
