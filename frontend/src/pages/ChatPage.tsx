import { useParams } from 'react-router-dom'
import { useGetCallQuery } from '../api/api'
import ChatBox from '../components/ChatBox/ChatBox'
import SummaryPanel from '../components/SummaryCard/SummaryPanel'

export default function ChatPage() {
  const { id = '' } = useParams()
  const { data, isLoading, isError } = useGetCallQuery(id)
  if (isLoading) return <p className="muted center">Loading…</p>
  if (isError || !data) return <p className="muted center">Call not found.</p>
  return (
    <div className="call-layout with-summary">
      <section className="call-main">
        <h1 className="call-title">{data.title ?? 'New call'}</h1>
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
