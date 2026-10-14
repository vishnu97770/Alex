import type { CallSummary, SummaryStatus } from '../../types/api'
import SummaryCard from './SummaryCard'

/** Right-hand summary column: spinner while generating, the card when ready, a message on failure. */
export default function SummaryPanel({
  summary,
  status,
}: {
  summary: CallSummary | null
  status: SummaryStatus
}) {
  return (
    <aside className="summary-panel" aria-label="Call summary">
      {summary ? (
        <SummaryCard summary={summary} />
      ) : status === 'FAILED' ? (
        <p className="muted">The summary could not be generated.</p>
      ) : (
        <p className="muted" role="status">
          <span className="spinner" aria-hidden /> Generating summary…
        </p>
      )}
    </aside>
  )
}
