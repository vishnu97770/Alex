import { useNavigate, useOutletContext } from 'react-router-dom'
import { useListAgentsQuery } from '../api/api'

export default function MyAgents() {
    const { me } = useOutletContext()
    const navigate = useNavigate()
    const { data: agents, isLoading, isError } = useListAgentsQuery(me.uid)
    return (
        <div className="page-column">
            <div className="page-top">
                <h1 className="page-title">{me.username}’s agents</h1>
                <button className="primary" onClick={() => navigate(`/create_agent/${me.uid}`)}>
                    Create new agent +
                </button>
            </div>
            <div className="page-body">
                <div className="agents-box">
                    {isLoading && <p className="muted">Loading…</p>}
                    {isError && (
                        <p role="alert" className="muted">
                            Could not load your agents.
                        </p>
                    )}
                    {agents?.length === 0 && <p className="muted">You have no agents yet.</p>}
                    {agents?.map((a) => (
                        <div className="agent-card" key={a.aid} data-testid="agent-card">
                            <div className="agent-card-top">
                                <span
                                    className={`status-dot ${a.status}`}
                                    role="img"
                                    aria-label={a.status === 'busy' ? 'Busy' : 'Free'}
                                    title={a.status === 'busy' ? 'Busy' : 'Free'}
                                />
                                <button
                                    className="icon-button"
                                    aria-label={`Edit ${a.name}`}
                                    onClick={() => navigate(`/agents/${me.uid}/update/${a.aid}`)}
                                >
                                    <svg
                                        viewBox="0 0 24 24"
                                        width="20"
                                        height="20"
                                        fill="currentColor"
                                        aria-hidden
                                    >
                                        <circle cx="12" cy="5" r="2" />
                                        <circle cx="12" cy="12" r="2" />
                                        <circle cx="12" cy="19" r="2" />
                                    </svg>
                                </button>
                            </div>
                            <div className="agent-card-name">{a.name}</div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    )
}
