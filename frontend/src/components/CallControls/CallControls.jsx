import { useAppSelector } from '../../app/hooks'
import { useCall } from '../../features/call/CallProvider'
const LABEL = {
    idle: 'Not connected',
    connecting: 'Connecting…',
    waiting_for_agent: 'Waiting for the agent…',
    connected: 'Connected',
    reconnecting: 'Reconnecting…',
    ended: 'Call ended',
    failed: 'Call failed',
}
export default function CallControls() {
    const { status, muted, error } = useAppSelector((s) => s.call)
    const { start, end, setMuted } = useCall()
    const live = ['connecting', 'waiting_for_agent', 'connected', 'reconnecting'].includes(status)
    return (
        <div className="controls">
            {error && (
                <div className="banner error" role="alert">
                    {error}
                </div>
            )}
            <div className="row">
                <span className={`dot ${status}`} aria-hidden />{' '}
                <span aria-live="polite">{LABEL[status]}</span>
            </div>
            <div className="row">
                {!live && (
                    <button className="primary" onClick={() => void start()}>
                        {status === 'idle' ? 'Start call' : 'Start a new call'}
                    </button>
                )}
                {live && (
                    <>
                        <button onClick={() => void setMuted(!muted)} aria-pressed={muted}>
                            {muted ? 'Unmute' : 'Mute'}
                        </button>
                        <button className="danger" onClick={() => void end()}>
                            End call
                        </button>
                    </>
                )}
            </div>
        </div>
    )
}
