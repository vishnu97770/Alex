import { Link } from 'react-router-dom'
import { useGetActiveProfileQuery, useGetCallQuery } from '../api/api'
import { useAppSelector } from '../app/hooks'
import ChatBox from '../components/ChatBox/ChatBox'
import CallControls from '../components/CallControls/CallControls'
import Sphere, { sphereMode } from '../components/Sphere/Sphere'
import SummaryCard from '../components/SummaryCard/SummaryCard'
import { useCall } from '../features/call/CallProvider'
import { selectEntries } from '../features/transcript/slice'
import { usePrefersReducedMotion } from '../lib/usePrefersReducedMotion'

export default function CallPage() {
  const { status, agentState, currentCallId } = useAppSelector((s) => s.call)
  const entries = useAppSelector(selectEntries)
  const { manager } = useCall()
  const reduced = usePrefersReducedMotion()
  const { data: profile } = useGetActiveProfileQuery()
  const ended = status === 'ended'
  const { data: call } = useGetCallQuery(currentCallId ?? '', { skip: !ended || !currentCallId })

  return (
    <div className="call">
      {profile && profile.placeholders.length > 0 && (
        <div className="banner warn">
          Your agent brief has {profile.placeholders.length} item(s) to fill in (e.g.{' '}
          {profile.placeholders[0]}). <Link to="/settings">Fill them in</Link>
        </div>
      )}
      <Sphere
        mode={sphereMode(status, agentState)}
        getLevels={() => manager.getLevels()}
        reducedMotion={reduced}
      />
      <ChatBox bubbles={entries} />
      {ended && !call?.summary && call?.summary_status !== 'FAILED' && (
        <p className="muted center">Generating summary…</p>
      )}
      {ended && call?.summary_status === 'FAILED' && (
        <p className="muted center">The summary could not be generated.</p>
      )}
      {ended && call?.summary && <SummaryCard summary={call.summary} />}
      <CallControls />
    </div>
  )
}
