import { useState } from 'react'
import { useGetScreenTimeQuery } from '../../api/api'
import LineChart from '../charts/LineChart'

export const formatHours = (h) => {
    const mins = Math.round(h * 60)
    if (mins < 60) return `${mins}m`
    return `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, '0')}m`
}

const shiftWeek = (iso, weeks) => {
    const d = new Date(`${iso}T00:00:00`)
    d.setDate(d.getDate() + weeks * 7)
    const p = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

/** Time spent in the app per weekday for one week (the current week by default), with navigation. */
export default function ScreenTime({ uid }) {
    const [weekStart, setWeekStart] = useState(null)
    const { data, isError } = useGetScreenTimeQuery({ uid, weekStart })
    const days = data?.days ?? []
    const todayIdx = days.findIndex((d) => d.date === data?.today)
    const elapsed = todayIdx >= 0 ? todayIdx + 1 : data && data.today < data.week_start ? 0 : days.length
    const total = days.reduce((a, d) => a + d.hours, 0)
    const average = elapsed ? total / elapsed : 0
    const isCurrent = todayIdx >= 0
    return (
        <section className="screen-time" aria-label="Screen time">
            <div className="screen-time-head">
                <div>
                    <h2>Screen time</h2>
                    <p className="muted">Daily average</p>
                    <p className="screen-time-average">{formatHours(average)}</p>
                </div>
                <div className="screen-time-nav">
                    <button
                        type="button"
                        aria-label="Previous week"
                        disabled={!data}
                        onClick={() => setWeekStart(shiftWeek(data.week_start, -1))}
                    >
                        ‹
                    </button>
                    <span className="muted">
                        {isCurrent ? 'This week' : data ? `Week of ${data.week_start}` : ''}
                    </span>
                    <button
                        type="button"
                        aria-label="Next week"
                        disabled={!data || isCurrent}
                        onClick={() => setWeekStart(shiftWeek(data.week_start, 1))}
                    >
                        ›
                    </button>
                </div>
            </div>
            {isError && (
                <p role="alert" className="muted">
                    Could not load your screen time.
                </p>
            )}
            {data && (
                <LineChart
                    labels={days.map((d) => d.weekday)}
                    tooltipTitles={days.map((d) => d.date)}
                    series={[
                        {
                            id: 'hours',
                            name: 'Time in app',
                            color: 'var(--chart-vivid)',
                            points: days.map((d) => d.hours),
                        },
                    ]}
                    integer={false}
                    minMax={1}
                    area
                    highlightIndex={todayIdx >= 0 ? todayIdx : null}
                    formatY={(v) => `${v}h`}
                    formatValue={formatHours}
                    ariaLabel="Hours in the app per weekday"
                />
            )}
        </section>
    )
}
