import UsageGraph from '../Dashboard/UsageGraph'

/** The same graph as the dashboard's, for one agent. */
export default function AgentGraphBox({ uid, agentId, colorIndex }) {
    return <UsageGraph uid={uid} agentId={agentId} colorIndex={colorIndex} />
}
