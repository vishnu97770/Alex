import { useState } from 'react'
import { useGetUsageQuery } from '../../api/api'
import LineChart, { seriesColor } from '../charts/LineChart'

const METRICS = [
    { value: 'calls', label: 'Calls Made' },
    { value: 'minutes', label: 'Minutes Talked' },
]
const RANGES = [
    { value: '28d', label: 'Last 28 days' },
    { value: '7d', label: 'Last 7 days' },
    { value: 'today', label: 'Today' },
]

/** X labels for the buckets the server returned: hours for "today", dates otherwise. */
export function bucketLabels(buckets, range) {
    return buckets.map((b) => {
        // The server sends ISO instants in the user's zone; the wall-clock part is what we show.
        const [date, rest] = b.split('T')
        if (range === 'today') return `${Number(rest.slice(0, 2))}:00`
        const [, m, d] = date.split('-').map(Number)
        return new Date(2000, m - 1, d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    })
}

/**
 * The metric / period bar on top, the chart with its legend below. `agentId` narrows it to one agent
 * (`colorIndex` keeps that agent's colour the same as on the dashboard).
 */
export default function UsageGraph({ uid, agentId, colorIndex = 0, title }) {
    const [metric, setMetric] = useState('calls')
    const [range, setRange] = useState('28d')
    const { data, isFetching, isError } = useGetUsageQuery({ uid, metric, range, agentId })
    const series = (data?.series ?? []).map((s, i) => ({
        ...s,
        color: seriesColor(agentId ? colorIndex : i),
    }))
    const minutes = metric === 'minutes'
    return (
        <div className="graph-box" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="graph-bar">
                {title && <span className="graph-title">{title}</span>}
                <select aria-label="Metric" value={metric} onChange={(e) => setMetric(e.target.value)}>
                    {METRICS.map((m) => (
                        <option key={m.value} value={m.value}>
                            {m.label}
                        </option>
                    ))}
                </select>
                <select aria-label="Time period" value={range} onChange={(e) => setRange(e.target.value)}>
                    {RANGES.map((r) => (
                        <option key={r.value} value={r.value}>
                            {r.label}
                        </option>
                    ))}
                </select>
            </div>
            <div className="graph-body" aria-busy={isFetching}>
                {isError && (
                    <p role="alert" className="muted">
                        Could not load the usage data.
                    </p>
                )}
                {data && (
                    <LineChart
                        labels={bucketLabels(data.buckets, range)}
                        series={series}
                        integer={!minutes}
                        minMax={minutes ? 10 : 4}
                        formatValue={(v) => (minutes ? `${v} min` : String(v))}
                        ariaLabel={`${minutes ? 'Minutes talked' : 'Calls made'}, ${RANGES.find((r) => r.value === range).label}`}
                    />
                )}
                {!data && !isError && <p className="muted">Loading…</p>}
            </div>
        </div>
    )
}
