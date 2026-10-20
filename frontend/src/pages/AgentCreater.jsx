import { useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { errorMessage, useCreateAgentMutation } from '../api/api'

export default function AgentCreater() {
    const { me } = useOutletContext()
    const navigate = useNavigate()
    const [name, setName] = useState('')
    const [role, setRole] = useState('')
    const [error, setError] = useState(null)
    const [createAgent, { isLoading }] = useCreateAgentMutation()
    const submit = async (e) => {
        e.preventDefault()
        setError(null)
        try {
            const a = await createAgent({
                uid: me.uid,
                name: name.trim(),
                role_behavior: role.trim(),
            }).unwrap()
            navigate(`/create_agent/${me.uid}/${a.aid}`)
        } catch (err) {
            setError(errorMessage(err))
        }
    }
    return (
        <div className="center-box-page">
            <form className="box wide-box" onSubmit={(e) => void submit(e)}>
                <h1>Create a new agent</h1>
                {error && (
                    <div className="banner error" role="alert">
                        {error}
                    </div>
                )}
                <label>
                    What would be the agent’s name?
                    <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
                </label>
                <label>
                    What would be the role and behaviour of the agent?
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
                        disabled={isLoading || name.trim() === '' || role.trim().length < 10}
                    >
                        {isLoading ? 'Creating…' : 'Create agent'}
                    </button>
                </div>
            </form>
        </div>
    )
}
