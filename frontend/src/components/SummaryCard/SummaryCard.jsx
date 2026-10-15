export default function SummaryCard({ summary }) {
    return (
        <article className="summary-card" aria-label="Call summary">
            <h2>{summary.title}</h2>
            <p>{summary.summary}</p>
            {summary.key_points.length > 0 && (
                <>
                    <h3>Key points</h3>
                    <ul>
                        {summary.key_points.map((k, i) => (
                            <li key={i}>{k}</li>
                        ))}
                    </ul>
                </>
            )}
            {summary.agent_commitments_and_next_actions.length > 0 && (
                <>
                    <h3>Next actions</h3>
                    <ul>
                        {summary.agent_commitments_and_next_actions.map((a, i) => (
                            <li key={i}>
                                {a.action}{' '}
                                <span className="muted">
                                    ({a.owner}
                                    {a.due_if_stated ? `, ${a.due_if_stated}` : ''})
                                </span>
                            </li>
                        ))}
                    </ul>
                </>
            )}
            <p className="muted">
                Outcome: {summary.call_outcome} · Sentiment: {summary.sentiment}
                {summary.escalation_needed ? ` · Escalation needed: ${summary.escalation_reason ?? ''}` : ''}
            </p>
        </article>
    )
}
