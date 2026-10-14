import { makeStore } from '../../app/store'
import { api } from '../../api/api'
import { callEnded, callStarting } from '../call/slice'

describe('summary polling listener', () => {
  afterEach(() => vi.restoreAllMocks())

  it('polls until the summary is READY, then refreshes the sidebar list', async () => {
    const replies = ['PENDING', 'PENDING', 'READY']
    const calls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (req: Request) => {
        const url = typeof req === 'string' ? req : req.url
        calls.push(url)
        const body = url.endsWith('/calls')
          ? []
          : {
              id: 'c1',
              title: 't',
              status: 'COMPLETED',
              summary_status: replies.shift() ?? 'READY',
              turns: [],
              summary: null,
            }
        return new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } })
      }),
    )
    const store = makeStore()
    store.dispatch(api.endpoints.listCalls.initiate())
    store.dispatch(callStarting('c1'))
    store.dispatch(callEnded('c1'))
    await vi.waitFor(() => expect(replies).toHaveLength(0), { timeout: 8000 })
    await vi.waitFor(
      () => expect(calls.filter((u) => u.endsWith('/calls')).length).toBeGreaterThanOrEqual(2),
      { timeout: 5000 },
    )
    expect(calls.filter((u) => u.includes('/calls/c1')).length).toBe(3)
  }, 15000)
})
