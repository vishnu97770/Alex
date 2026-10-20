import { useCallback, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { useListAgentsQuery } from '../api/api'
import AgentInfo from '../components/Agents/AgentInfo'

export default function MyAgents() {
    const { me } = useOutletContext()
    const navigate = useNavigate()
    const { data: agents, isLoading, isError } = useListAgentsQuery(me.uid)
    const [openAid, setOpenAid] = useState(null)
    const close = useCallback(() => setOpenAid(null), [])
    const openIndex = agents?.findIndex((a) => a.aid === openAid) ?? -1
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
                        <div
                            className="agent-card clickable"
                            key={a.aid}
                            data-testid="agent-card"
                            onClick={() => setOpenAid(a.aid)}
                        >
                            <div className="agent-card-top">
                                <span
                                    className={`status-dot ${a.status}`}
                                    role="img"
                                    aria-label={a.status === 'busy' ? 'Busy' : 'Free'}
                                    title={a.status === 'busy' ? 'Busy' : 'Free'}
                                    onClick={(e) => e.stopPropagation()}
                                />
                                <button
                                    className="icon-button"
                                    aria-label={`Edit ${a.name}`}
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        navigate(`/agents/${me.uid}/update/${a.aid}`)
                                    }}
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
                            {/* the click is handled by the card; the button makes the card reachable by keyboard */}
                            <button type="button" className="agent-card-name" aria-label={`Open ${a.name}`}>
                                {a.name}
                            </button>
                        </div>
                    ))}
                </div>
            </div>
            {openIndex >= 0 && (
                <AgentInfo uid={me.uid} agent={agents[openIndex]} colorIndex={openIndex} onClose={close} />
            )}
        </div>
    )
}
