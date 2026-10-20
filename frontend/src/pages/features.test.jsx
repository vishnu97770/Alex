import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { makeStore } from '../app/store'
import { routes } from '../app/router'
import { callStarting, muteChanged, statusChanged } from '../features/call/slice'

const setMuted = vi.fn()
vi.mock('../features/call/CallProvider', () => ({
    CallProvider: ({ children }) => children,
    useCall: () => ({
        manager: { getLevels: () => ({ user: 0, agent: 0 }) },
        start: vi.fn(),
        end: vi.fn(),
        setMuted: (m) => setMuted(m),
    }),
}))
vi.mock('./Landing', () => ({ default: () => <div /> }))
vi.mock('../components/Sphere/Sphere', () => ({
    default: () => <div data-testid="sphere" />,
    sphereMode: () => 'idle',
}))

const ME = { uid: 'u1', username: 'Ann', email: 'ann@example.com', avatar_url: null, agent_count: 2 }
const json = (b, status = 200) =>
    new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })
const AGENTS = [
    { aid: 'a1', name: 'Ava', role_behavior: 'Books appointments', status: 'free', lifecycle: 'ACTIVE' },
    { aid: 'a2', name: 'Ben', role_behavior: 'Answers calls', status: 'busy', lifecycle: 'ACTIVE' },
]
const usage = (agentId) => ({
    metric: 'calls',
    range: '28d',
    tz: 'UTC',
    buckets: Array.from(
        { length: 28 },
        (_, i) => `2026-09-${String(23 + (i % 7)).padStart(2, '0')}T00:00:00+00:00`,
    ),
    series: agentId
        ? [{ id: agentId, name: 'Ava', kind: 'agent', points: Array(28).fill(0) }]
        : [
              { id: 'a1', name: 'Ava', kind: 'agent', points: Array(28).fill(0) },
              { id: 'manager', name: 'Manager', kind: 'manager', points: Array(28).fill(1) },
          ],
})

function mockApi(handlers) {
    const seen = []
    vi.stubGlobal(
        'fetch',
        vi.fn(async (req) => {
            const u = new URL(req.url)
            const key = `${req.method} ${u.pathname.replace('/api/v1', '')}`
            seen.push({ key, search: u.searchParams })
            const h = handlers[key]
            return h ? h(req, u) : json({ error: { message: 'nope' } }, 404)
        }),
    )
    return seen
}
const base = {
    'GET /auth/me': () => json(ME),
    'GET /users/u1/agents': () => json(AGENTS),
    'GET /users/u1/stats/usage': (_r, u) => json(usage(u.searchParams.get('agent_id'))),
}
function renderAt(path, store = makeStore()) {
    const router = createMemoryRouter(routes, { initialEntries: [path] })
    render(
        <Provider store={store}>
            <RouterProvider router={router} />
        </Provider>,
    )
    return { router, store }
}
afterEach(() => {
    vi.unstubAllGlobals()
    setMuted.mockClear()
})

describe('dashboard graph', () => {
    it('queries all agents with the chosen metric and period, and lists every series in the legend', async () => {
        const seen = mockApi(base)
        renderAt('/dashboard/u1')
        const legend = await screen.findByRole('list', { name: 'Legend' })
        expect(legend).toHaveTextContent('Ava')
        expect(legend).toHaveTextContent('Manager')
        await userEvent.selectOptions(screen.getByLabelText('Metric'), 'minutes')
        await userEvent.selectOptions(screen.getByLabelText('Time period'), 'today')
        await waitFor(() => {
            const last = seen.filter((s) => s.key.endsWith('/stats/usage')).at(-1).search
            expect([last.get('metric'), last.get('range'), last.get('agent_id')]).toEqual([
                'minutes',
                'today',
                null,
            ])
        })
    })
})

describe('agent info pop-up', () => {
    it('opens from the card, is read-only, and shows only that agent in its graph', async () => {
        const seen = mockApi(base)
        renderAt('/agents/u1')
        await userEvent.click((await screen.findAllByTestId('agent-card'))[0])
        const dialog = await screen.findByRole('dialog', { name: /agent info/i })
        expect(within(dialog).getByText('Books appointments')).toBeInTheDocument()
        expect(within(dialog).queryByRole('textbox')).toBeNull()
        expect(within(dialog).queryByRole('button', { name: /save/i })).toBeNull()
        await waitFor(() =>
            expect(
                seen.some((s) => s.key.endsWith('/stats/usage') && s.search.get('agent_id') === 'a1'),
            ).toBe(true),
        )
    })
    it('the edit button and status dot do not open it; Escape, backdrop and Close do close it', async () => {
        mockApi(base)
        const { router } = renderAt('/agents/u1')
        const card = (await screen.findAllByTestId('agent-card'))[0]
        await userEvent.click(within(card).getByRole('img', { name: /free/i }))
        expect(screen.queryByRole('dialog')).toBeNull()
        await userEvent.click(within(card).getByRole('button', { name: 'Edit Ava' }))
        expect(screen.queryByRole('dialog')).toBeNull()
        expect(router.state.location.pathname).toBe('/agents/u1/update/a1')
        router.navigate('/agents/u1')
        const again = (await screen.findAllByTestId('agent-card'))[0]
        await userEvent.click(again)
        await screen.findByRole('dialog')
        await userEvent.keyboard('{Escape}')
        expect(screen.queryByRole('dialog')).toBeNull()
        await userEvent.click(again)
        await userEvent.click(screen.getByRole('dialog').parentElement) // the backdrop
        expect(screen.queryByRole('dialog')).toBeNull()
        await userEvent.click(again)
        await userEvent.click(screen.getByRole('button', { name: 'Close' }))
        expect(screen.queryByRole('dialog')).toBeNull()
        expect(document.body.style.overflow).toBe('')
    })
})

describe('profile screen time', () => {
    it('shows the daily average from the server data', async () => {
        mockApi({
            ...base,
            'GET /users/u1/screen-time': () =>
                json({
                    week_start: '2026-10-19',
                    today: '2026-10-20',
                    days: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((w, i) => ({
                        date: `2026-10-${19 + i}`,
                        weekday: w,
                        hours: i === 0 ? 1 : i === 1 ? 2 : 0,
                    })),
                }),
        })
        renderAt('/profile/u1')
        expect(await screen.findByText('1h 30m')).toBeInTheDocument() // (1h + 2h) / 2 elapsed days
        expect(screen.getByRole('img', { name: /hours in the app/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Next week' })).toBeDisabled()
    })
})

describe('settings', () => {
    afterEach(() => {
        localStorage.clear()
        document.documentElement.removeAttribute('style')
    })
    it('changes accent colour, font size and font, and keeps the theme switch', async () => {
        mockApi(base)
        renderAt('/settings/u1')
        await userEvent.click(await screen.findByRole('button', { name: '#4f8cff' }))
        expect(document.documentElement.style.getPropertyValue('--brand')).toBe('#4f8cff')
        await userEvent.click(screen.getByRole('radio', { name: 'Large' }))
        expect(document.documentElement.style.fontSize).toBe('18px')
        await userEvent.selectOptions(screen.getByLabelText('Font'), 'open-sans')
        expect(document.documentElement.style.getPropertyValue('--font-sans')).toContain('Open Sans Variable')
        expect(screen.getByRole('switch', { name: 'Theme' })).toBeInTheDocument()
        expect(screen.queryByRole('option', { name: /dyslexic|anthropic/i })).toBeNull()
    })
})

describe('manager: old calls during a live call', () => {
    const CALLS = [
        { id: 'c1', title: 'First', status: 'COMPLETED', summary_status: 'READY', started_at: null },
        { id: 'c2', title: 'Second', status: 'COMPLETED', summary_status: 'READY', started_at: null },
    ]
    const callDetail = (id, title) => ({
        id,
        title,
        summary_status: 'READY',
        turns: [{ seq: 0, speaker: 'agent', text: `Transcript of ${title}`, is_final: true }],
        summary: null,
    })
    const api = {
        ...base,
        'GET /users/u1/manager/calls': () => json(CALLS),
        'GET /calls/c1': () => json(callDetail('c1', 'First')),
        'GET /calls/c2': () => json(callDetail('c2', 'Second')),
    }
    const goLive = (store) =>
        act(() => {
            store.dispatch(callStarting('live1'))
            store.dispatch(statusChanged('connected'))
        })

    it('not on a call: an old call opens normally', async () => {
        mockApi(api)
        const { router } = renderAt('/manager/u1')
        await userEvent.click(await screen.findByRole('link', { name: 'First' }))
        expect(router.state.location.pathname).toBe('/manager/u1/chats/c1')
        expect(screen.queryByRole('menu')).toBeNull()
    })

    it('on a call: offers full or split view, keeps the call, and replaces one old call with another', async () => {
        mockApi(api)
        const { router, store } = renderAt('/manager/u1')
        const first = await screen.findByRole('link', { name: 'First' })
        goLive(store)
        await userEvent.click(first)
        const menu = await screen.findByRole('menu')
        expect(
            within(menu)
                .getAllByRole('menuitem')
                .map((b) => b.textContent),
        ).toEqual(['Full view', 'Split view'])
        expect(router.state.location.pathname).toBe('/manager/u1') // the call page is not left
        await userEvent.click(within(menu).getByRole('menuitem', { name: 'Split view' }))
        expect(await screen.findByText('Transcript of First')).toBeInTheDocument()
        expect(screen.getByTestId('sphere')).toBeInTheDocument() // the live call is still on screen
        expect(setMuted).not.toHaveBeenCalled()
        // another old call replaces it: no menu, a single old-call panel
        await userEvent.click(screen.getByRole('link', { name: 'Second' }))
        expect(screen.queryByRole('menu')).toBeNull()
        expect(await screen.findByText('Transcript of Second')).toBeInTheDocument()
        expect(screen.queryByText('Transcript of First')).toBeNull()
        expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
        expect(store.getState().call.status).toBe('connected')
    })

    it('full view hides the live call, mutes the microphone, and "Back to call" restores everything', async () => {
        mockApi(api)
        const { store } = renderAt('/manager/u1')
        const first = await screen.findByRole('link', { name: 'First' })
        goLive(store)
        await userEvent.click(first)
        await userEvent.click(await screen.findByRole('menuitem', { name: 'Full view' }))
        expect(await screen.findByText('Transcript of First')).toBeInTheDocument()
        expect(screen.queryByTestId('sphere')).toBeNull()
        expect(setMuted).toHaveBeenCalledWith(true)
        act(() => void store.dispatch(muteChanged(true)))
        await userEvent.click(screen.getByRole('button', { name: 'Back to call' }))
        expect(await screen.findByTestId('sphere')).toBeInTheDocument()
        expect(setMuted).toHaveBeenLastCalledWith(false)
        expect(store.getState().call.status).toBe('connected')
    })

    it('when the call ends the old call closes and the normal layout returns', async () => {
        mockApi(api)
        const { store } = renderAt('/manager/u1')
        const first = await screen.findByRole('link', { name: 'First' })
        goLive(store)
        await userEvent.click(first)
        await userEvent.click(await screen.findByRole('menuitem', { name: 'Split view' }))
        await screen.findByText('Transcript of First')
        act(() => void store.dispatch(statusChanged('ended')))
        await waitFor(() => expect(screen.queryByText('Transcript of First')).toBeNull())
        expect(screen.getByTestId('sphere')).toBeInTheDocument()
    })
})
