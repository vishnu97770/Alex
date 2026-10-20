import { useId, useState } from 'react'

const W = 720
const H = 300
const PAD = { top: 16, right: 16, bottom: 32, left: 44 }

/** Round tick step: 1, 2 or 5 times a power of ten (integers only when `integer`). */
export function niceStep(max, count = 4, integer = true) {
    const raw = max / count
    const pow = 10 ** Math.floor(Math.log10(raw))
    const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw) ?? raw
    return integer ? Math.max(1, Math.ceil(step)) : step
}

/** Y ticks from 0 up to the first tick at or above `max` (at least `minMax`, so empty data still has a scale). */
export function niceTicks(max, { integer = true, minMax = integer ? 4 : 1 } = {}) {
    const top = Math.max(max, minMax)
    const step = niceStep(top, 4, integer)
    const ticks = []
    for (let v = 0; v < top + step * 0.999; v += step) ticks.push(Math.round(v * 1e6) / 1e6)
    return ticks
}

/** Palette slot for series `i`; the slots are CSS variables so they follow light/dark. */
export const seriesColor = (i) => `var(--chart-${(i % 8) + 1})`

/**
 * Responsive inline-SVG line chart. Points are joined by straight segments (no smoothing), so peaks
 * are spikes. `series`: [{ id, name, color, points: number[] }]; `labels`: one X label per point.
 */
export default function LineChart({
    labels,
    series,
    tooltipTitles,
    formatY = (v) => String(v),
    formatValue = formatY,
    integer = true,
    minMax,
    highlightIndex = null,
    area = false,
    ariaLabel = 'Line chart',
}) {
    const uid = useId()
    const [hover, setHover] = useState(null)
    const n = labels.length
    const max = Math.max(0, ...series.flatMap((s) => s.points))
    const ticks = niceTicks(max, { integer, ...(minMax !== undefined ? { minMax } : {}) })
    const yMax = ticks[ticks.length - 1]
    const iw = W - PAD.left - PAD.right
    const ih = H - PAD.top - PAD.bottom
    const x = (i) => PAD.left + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw)
    const y = (v) => PAD.top + ih - (v / yMax) * ih
    const every = Math.max(1, Math.ceil(n / 8)) // keep X labels from colliding
    const onMove = (e) => {
        const r = e.currentTarget.getBoundingClientRect()
        const px = ((e.clientX - r.left) / r.width) * W
        const i = n <= 1 ? 0 : Math.round(((px - PAD.left) / iw) * (n - 1))
        setHover(Math.min(n - 1, Math.max(0, i)))
    }
    const hasData = max > 0
    return (
        <figure className="line-chart">
            <div className="chart-plot">
                <svg
                    viewBox={`0 0 ${W} ${H}`}
                    role="img"
                    aria-label={ariaLabel}
                    onMouseMove={onMove}
                    onMouseLeave={() => setHover(null)}
                >
                    {ticks.map((t) => (
                        <g key={t}>
                            <line
                                className="chart-grid"
                                x1={PAD.left}
                                x2={W - PAD.right}
                                y1={y(t)}
                                y2={y(t)}
                            />
                            <text
                                className="chart-tick"
                                x={PAD.left - 8}
                                y={y(t)}
                                textAnchor="end"
                                dy="0.32em"
                            >
                                {formatY(t)}
                            </text>
                        </g>
                    ))}
                    {labels.map((l, i) =>
                        i % every === 0 || i === highlightIndex ? (
                            <text
                                key={i}
                                className={`chart-tick ${i === highlightIndex ? 'today' : ''}`}
                                x={x(i)}
                                y={H - 10}
                                textAnchor="middle"
                            >
                                {l}
                            </text>
                        ) : null,
                    )}
                    {highlightIndex !== null && highlightIndex < n && (
                        <line
                            className="chart-today"
                            x1={x(highlightIndex)}
                            x2={x(highlightIndex)}
                            y1={PAD.top}
                            y2={PAD.top + ih}
                        />
                    )}
                    {series.map((s) => (
                        <g key={s.id} style={{ color: s.color }}>
                            {area && n > 1 && (
                                <>
                                    <defs>
                                        <linearGradient id={`${uid}-${s.id}`} x1="0" x2="0" y1="0" y2="1">
                                            <stop offset="0" stopColor="currentColor" stopOpacity="0.35" />
                                            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
                                        </linearGradient>
                                    </defs>
                                    <polygon
                                        fill={`url(#${uid}-${s.id})`}
                                        points={`${x(0)},${y(0)} ${s.points.map((v, i) => `${x(i)},${y(v)}`).join(' ')} ${x(n - 1)},${y(0)}`}
                                    />
                                </>
                            )}
                            <polyline
                                className="chart-line"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinejoin="miter"
                                strokeLinecap="butt"
                                points={s.points.map((v, i) => `${x(i)},${y(v)}`).join(' ')}
                            />
                            {n === 1 && <circle cx={x(0)} cy={y(s.points[0])} r="4" fill="currentColor" />}
                            {hover !== null && (
                                <circle
                                    className="chart-point"
                                    cx={x(hover)}
                                    cy={y(s.points[hover])}
                                    r="4.5"
                                    fill="currentColor"
                                />
                            )}
                        </g>
                    ))}
                    {hover !== null && (
                        <line
                            className="chart-cursor"
                            x1={x(hover)}
                            x2={x(hover)}
                            y1={PAD.top}
                            y2={PAD.top + ih}
                        />
                    )}
                </svg>
                {hover !== null && (
                    <div
                        className="chart-tooltip"
                        role="status"
                        style={{
                            left: `${(x(hover) / W) * 100}%`,
                            transform: `translateX(${hover > n / 2 ? '-105%' : '5%'})`,
                        }}
                    >
                        <strong>{tooltipTitles?.[hover] ?? labels[hover]}</strong>
                        {series.map((s) => (
                            <div key={s.id} className="chart-tooltip-row">
                                <span className="swatch" style={{ background: s.color }} aria-hidden />
                                <span>{s.name}</span>
                                <span>{formatValue(s.points[hover])}</span>
                            </div>
                        ))}
                    </div>
                )}
                {!hasData && <p className="chart-empty muted">No data for this period yet.</p>}
            </div>
            <figcaption>
                <ul className="chart-legend" aria-label="Legend">
                    {series.map((s) => (
                        <li key={s.id}>
                            <span className="swatch" style={{ background: s.color }} aria-hidden />
                            {s.name}
                        </li>
                    ))}
                </ul>
            </figcaption>
        </figure>
    )
}
