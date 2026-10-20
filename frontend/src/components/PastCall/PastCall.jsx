import { useGetCallQuery } from '../../api/api'
import ChatBox from '../ChatBox/ChatBox'
import SummaryPanel from '../SummaryCard/SummaryPanel'

/** An old call: transcript in the main column, summary beside it (below it when `compact`). */
export default function PastCall({ id, compact = false, onClose }) {
    const { data, isLoading, isError } = useGetCallQuery(id)
    if (isLoading) return <p className="muted center">Loading…</p>
    if (isError || !data) return <p className="muted center">Call not found.</p>
    return (
        <div className={`call-layout with-summary ${compact ? 'compact' : ''}`}>
            <section className="call-main">
                <div className="past-call-head">
                    <h1 className="call-title">{data.title ?? 'New call'}</h1>
                    {onClose && (
                        <button type="button" onClick={onClose} aria-label="Close this call">
                            Close
                        </button>
                    )}
                </div>
                <ChatBox
                    bubbles={data.turns.map((t) => ({
                        id: String(t.seq),
                        speaker: t.speaker,
                        text: t.text,
                        isFinal: t.is_final,
                    }))}
                />
            </section>
            <SummaryPanel summary={data.summary} status={data.summary_status} />
        </div>
    )
}
