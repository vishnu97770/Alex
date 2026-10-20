import UsageGraph from './UsageGraph'

/** Dashboard graph: every agent (and the manager) in one chart. */
export default function GraphBox({ uid }) {
    return <UsageGraph uid={uid} />
}
