import { useParams } from 'react-router-dom'
import { useGetCallQuery } from '../api/api'
import ChatBox from '../components/ChatBox/ChatBox'
import SummaryCard from '../components/SummaryCard/SummaryCard'

export default function ChatPage() {
  const { id = '' } = useParams()
  const { data, isLoading, isError } = useGetCallQuery(id, {
    pollingInterval: 0,
  })
  if (isLoading) return <p className="muted center">Loading…</p>
  if (isError || !data) return <p className="muted center">Call not found.</p>
  return (
    <div className="call readonly">
      <h1>{data.title ?? 'New call'}</h1>
      <ChatBox
        bubbles={data.turns.map((t) => ({
          id: String(t.seq),
          speaker: t.speaker,
          text: t.text,
          isFinal: t.is_final,
        }))}
      />
      {data.summary ? (
        <SummaryCard summary={data.summary} />
      ) : (
        <p className="muted center">
          {data.summary_status === 'PENDING' ? 'Summary is being generated…' : 'No summary available.'}
        </p>
      )}
    </div>
  )
}
