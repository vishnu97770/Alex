import reducer, {
  agentStateChanged,
  callEnded,
  callFailed,
  callReset,
  callStarting,
  muteChanged,
  statusChanged,
} from './slice'
describe('call slice', () => {
  it('starts, connects, tracks agent state and mute', () => {
    let s = reducer(undefined, callStarting('c1'))
    expect(s).toMatchObject({ status: 'connecting', currentCallId: 'c1', error: null })
    s = reducer(s, statusChanged('connected'))
    s = reducer(s, agentStateChanged('speaking'))
    s = reducer(s, muteChanged(true))
    expect(s).toMatchObject({ status: 'connected', agentState: 'speaking', muted: true })
  })
  it('failure records error and resets agent state', () => {
    const s = reducer(reducer(undefined, agentStateChanged('speaking')), callFailed('boom'))
    expect(s).toMatchObject({ status: 'failed', error: 'boom', agentState: 'idle' })
  })
  it('end keeps call id so the summary can be polled', () => {
    const s = reducer(reducer(undefined, callStarting('c1')), callEnded('c1'))
    expect(s).toMatchObject({ status: 'ended', currentCallId: 'c1' })
  })
  it('a new call clears the previous error', () => {
    const failed = reducer(undefined, callFailed('x'))
    expect(reducer(failed, callStarting('c2')).error).toBeNull()
    expect(reducer(failed, callReset()).status).toBe('idle')
  })
})
