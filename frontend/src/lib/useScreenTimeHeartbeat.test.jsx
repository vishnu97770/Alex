import { renderHook } from '@testing-library/react'
import { Provider } from 'react-redux'
import { makeStore } from '../app/store'
import { BEAT_MS, useScreenTimeHeartbeat } from './useScreenTimeHeartbeat'

const wrapper = ({ children }) => <Provider store={makeStore()}>{children}</Provider>
const setVisibility = (v) => {
    Object.defineProperty(document, 'visibilityState', { value: v, configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
}
const beats = (f) => f.mock.calls.filter(([r]) => r.url.endsWith('/screen-time/heartbeat'))

beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal(
        'fetch',
        vi.fn(async () => new Response(null, { status: 204 })),
    )
    setVisibility('visible')
})
afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
})

it('sends a beat every 30 s while visible, none while hidden, and nothing without a user', async () => {
    renderHook(() => useScreenTimeHeartbeat('u1'), { wrapper })
    await vi.advanceTimersByTimeAsync(BEAT_MS)
    expect(beats(fetch)).toHaveLength(1)
    expect(await beats(fetch)[0][0].json()).toMatchObject({ seconds: 30 })
    setVisibility('hidden') // flushes the 0 s remainder: nothing to send
    await vi.advanceTimersByTimeAsync(BEAT_MS * 3)
    expect(beats(fetch)).toHaveLength(1)
    setVisibility('visible')
    await vi.advanceTimersByTimeAsync(BEAT_MS)
    expect(beats(fetch)).toHaveLength(2)
    fetch.mockClear()
    renderHook(() => useScreenTimeHeartbeat(undefined), { wrapper })
    await vi.advanceTimersByTimeAsync(BEAT_MS * 2)
    expect(beats(fetch)).toHaveLength(2) // only the first hook's beats
})
