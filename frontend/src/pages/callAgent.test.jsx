import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { checkCallForm, normalizeAmount, normalizePhone } from '../components/CallAgent/CallAgent'
import { routes } from '../app/router'
import { makeStore } from '../app/store'
import { csvUploaded } from '../features/bulk/slice'
import { statusChanged } from '../features/call/slice'

vi.mock('./Landing', () => ({ default: () => <div /> }))
// WebGL is not available in jsdom: keep the real sphereMode, render the mode instead of the canvas.
vi.mock('../components/Sphere/Sphere', async (orig) => ({
    ...(await orig()),
    default: ({ mode }) => <div data-testid="sphere" data-mode={mode} />,
}))
// A fake LiveKit room: records the token it joined with and lets the test drive the callbacks.
const room = vi.hoisted(() => ({ joined: [], cb: null, disconnects: 0 }))
vi.mock('../lib/livekit/roomManager', () => ({
    CallRoomManager: class {
        getLevels() {
            return { user: 0, agent: 0 }
        }
        async connect(url, token, cb, opts) {
            room.joined.push({ url, token })
            room.opts = opts
            room.cb = cb
            cb.onStatus('connecting')
        }
        async setMuted() {}
        async disconnect() {
            room.disconnects += 1
        }
    },
}))

const ME = { uid: 'u1', username: 'Ann', email: 'ann@example.com', avatar_url: null, agent_count: 1 }
const AGENT = {
    aid: 'a1',
    name: 'Ava',
    role: 'Loan-Recovery Agent',
    voice: 'male',
    status: 'free',
    system_prompt: 'You are Ava, a Loan-Recovery Agent.',
    created_at: '2026-11-18T10:00:00Z',
}
const SUMMARY = {
    title: 'Asha agreed to pay',
    summary: 'Asha will pay the pending amount by Friday.',
    key_points: ['Missed October EMI'],
    agent_commitments_and_next_actions: [
        { action: 'Confirm payment', owner: 'lender', due_if_stated: 'Friday' },
    ],
    call_outcome: 'promise_to_pay',
    sentiment: 'neutral',
    escalation_needed: false,
}
const json = (b, status = 200) =>
    new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })

function mockApi(handlers) {
    const seen = []
    vi.stubGlobal(
        'fetch',
        vi.fn(async (req) => {
            const u = new URL(req.url)
            const key = `${req.method} ${u.pathname.replace('/api/v1', '')}`
            seen.push({ key, req })
            const h = handlers[key]
            return h ? h(req, u) : json({ error: { message: 'nope' } }, 404)
        }),
    )
    return seen
}
const backend = (agent = AGENT, extra = {}) =>
    mockApi({
        'GET /auth/me': () => json(ME),
        'GET /users/u1/agent': () => json(agent),
        'GET /users/u1/stats/calls-per-day': () => json({ days: [] }),
        'POST /users/u1/collections/calls': () =>
            json({ call_id: 'c1', livekit_url: 'wss://lk', token: 'tok-1' }),
        'POST /calls/c1/end': () => json({ status: 'ending' }),
        ...extra,
    })
function renderAt(path, store = makeStore()) {
    const router = createMemoryRouter(routes, { initialEntries: [path] })
    render(
        <Provider store={store}>
            <RouterProvider router={router} />
        </Provider>,
    )
    return { router, store }
}
const posts = (seen) => seen.filter((c) => c.key === 'POST /users/u1/collections/calls')
async function openMenu() {
    await userEvent.click(await screen.findByRole('button', { name: 'Call Agent' }))
    return screen.getByRole('menu', { name: 'Type of call' })
}
async function openIndividual() {
    await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: /Individual Call/ }))
    return screen.getByRole('dialog', { name: 'Individual Call' })
}

beforeEach(() => {
    room.joined = []
    room.cb = null
    room.disconnects = 0
})
afterEach(() => vi.unstubAllGlobals())

describe('call form validation', () => {
    it('accepts phone numbers with a country code and amounts with up to 2 decimals', () => {
        expect(normalizePhone('+91 98765-43210')).toBe('+919876543210')
        expect(normalizePhone('(+1) 555.123.4567')).toBe('+15551234567')
        for (const bad of ['12345', '0123456789', 'abcdefghijk', '+91 98765 43210 12345'])
            expect(normalizePhone(bad)).toBeNull()
        expect(normalizeAmount('12,000')).toBe('12000.00')
        expect(normalizeAmount('₹ 5200.5')).toBe('5200.50')
        for (const bad of ['0', '-5', '10.123', 'abc', '2000000000']) expect(normalizeAmount(bad)).toBeNull()
        expect(
            Object.keys(checkCallForm({ name: ' ', phone: '', amount: '', deadline: '', context: ' ' })),
        ).toEqual(['name', 'phone', 'amount', 'deadline', 'context'])
        expect(
            checkCallForm({
                name: 'Asha Rao',
                phone: '+919876543210',
                amount: '1',
                deadline: '2026-11-30',
                context: 'ok',
            }),
        ).toEqual({})
        // the server refuses a one-letter name, so the form says so first
        expect(checkCallForm({ name: 'A', phone: '', amount: '', deadline: '', context: '' }).name).toMatch(
            /full name/,
        )
    })
})

describe('your agent: Call Agent button', () => {
    it('is not shown before the agent is created', async () => {
        backend(null)
        renderAt('/agent/u1')
        expect(await screen.findByRole('button', { name: '+ Create Agent' })).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Call Agent' })).toBeNull()
    })

    it('sits right of the agent tile and offers exactly Individual Call and Bulk Call', async () => {
        backend()
        renderAt('/agent/u1')
        const tile = await screen.findByRole('button', { name: /^Ava, Free/ })
        const button = screen.getByRole('button', { name: 'Call Agent' })
        expect(tile.parentElement).toBe(button.closest('.agent-row') ?? null)
        expect(button).toHaveAttribute('aria-expanded', 'false')
        const menu = await openMenu()
        expect(button).toHaveAttribute('aria-expanded', 'true')
        expect(
            within(menu)
                .getAllByRole('menuitem')
                .map((i) => i.textContent),
        ).toEqual([expect.stringMatching(/^Individual Call/), expect.stringMatching(/^Bulk Call/)])
        await userEvent.keyboard('{Escape}')
        expect(screen.queryByRole('menu')).toBeNull()
        expect(button).toHaveFocus()
    })
})

describe('individual call', () => {
    it('opens a pop-up with name, phone, pending amount, deadline and call context; Cancel closes it and calls no one', async () => {
        const seen = backend()
        renderAt('/agent/u1')
        const dialog = await openIndividual()
        expect(within(dialog).getByLabelText('Client name')).toHaveFocus()
        expect(within(dialog).getByLabelText('Phone number')).toBeInTheDocument()
        expect(within(dialog).getByLabelText('Payment deadline')).toHaveAttribute('type', 'date')
        expect(within(dialog).getByLabelText('Pending amount')).toBeInTheDocument()
        expect(within(dialog).getByLabelText('Call context').tagName).toBe('TEXTAREA')
        expect(within(dialog).getByText('The agent will speak in its male voice.')).toBeInTheDocument()
        await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
        expect(screen.queryByRole('dialog')).toBeNull()
        expect(screen.getByRole('button', { name: /^Ava, Free/ })).toBeInTheDocument()
        expect(posts(seen)).toHaveLength(0)
    })

    it('shows every validation error and does not start a call with invalid input', async () => {
        const seen = backend()
        renderAt('/agent/u1')
        const dialog = await openIndividual()
        await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm Call' }))
        expect(within(dialog).getByText('Enter the client’s name.')).toBeInTheDocument()
        expect(within(dialog).getByText(/Enter the client’s phone number/)).toBeInTheDocument()
        expect(within(dialog).getByText('Choose the payment deadline.')).toBeInTheDocument()
        expect(within(dialog).getByText('Enter the pending amount.')).toBeInTheDocument()
        expect(within(dialog).getByText(/Add some context/)).toBeInTheDocument()
        await userEvent.type(within(dialog).getByLabelText('Phone number'), '12345')
        await userEvent.type(within(dialog).getByLabelText('Pending amount'), '-4')
        await userEvent.type(within(dialog).getByLabelText('Call context'), 'Missed two EMIs')
        await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm Call' }))
        expect(within(dialog).getByLabelText('Phone number')).toHaveAttribute('aria-invalid', 'true')
        expect(within(dialog).getByText(/valid phone number/)).toBeInTheDocument()
        expect(within(dialog).getByText(/greater than zero/)).toBeInTheDocument()
        expect(posts(seen)).toHaveLength(0)
    })

    it('Confirm sends the client details to the agent, opens the Call Page, and shows the summary after hang-up', async () => {
        let summaryReady = false
        const seen = backend(AGENT, {
            'GET /calls/c1': () =>
                json({
                    id: 'c1',
                    summary_status: summaryReady ? 'READY' : 'PENDING',
                    summary: summaryReady ? SUMMARY : null,
                    turns: [],
                }),
        })
        const { router } = renderAt('/agent/u1')
        const dialog = await openIndividual()
        await userEvent.type(within(dialog).getByLabelText('Client name'), 'Asha Rao')
        fireEvent.change(within(dialog).getByLabelText('Payment deadline'), {
            target: { value: '2026-11-30' },
        })
        await userEvent.type(within(dialog).getByLabelText('Phone number'), '+91 98123 45678')
        await userEvent.type(within(dialog).getByLabelText('Pending amount'), '12,000')
        expect(within(dialog).getByText(/12,000\.00/)).toBeInTheDocument() // shown as currency
        await userEvent.type(
            within(dialog).getByLabelText('Call context'),
            'Asha Rao{Enter}Missed the October EMI',
        )
        const confirm = within(dialog).getByRole('button', { name: 'Confirm Call' })
        await userEvent.dblClick(confirm)

        // one call, carrying exactly what was entered (normalised), to the agent's call endpoint
        await waitFor(() => expect(router.state.location.pathname).toBe('/call/u1'))
        expect(posts(seen)).toHaveLength(1)
        expect(await posts(seen)[0].req.json()).toEqual({
            borrower_name: 'Asha Rao',
            phone: '+919812345678',
            amount: '12000.00',
            currency: 'INR',
            due_date: '2026-11-30',
            context: 'Asha Rao\nMissed the October EMI',
            mode: 'web', // phone calls are not set up in this test
        })
        expect(room.joined).toEqual([{ url: 'wss://lk', token: 'tok-1' }]) // the room the server created for it
        expect(screen.queryByRole('dialog')).toBeNull()

        // Call Page: client header, sphere follows the call, conversation in order
        expect(screen.getByRole('heading', { name: 'Individual call' })).toBeInTheDocument()
        expect(screen.getByText(/5678/)).toHaveTextContent('••••••••5678')
        expect(screen.getByTestId('sphere')).toHaveAttribute('data-mode', 'connecting')
        act(() => {
            room.cb.onStatus('connected')
            room.cb.onAgentState('speaking')
            room.cb.onSegment({
                id: 's1',
                speaker: 'agent',
                text: 'Hello, who am I speaking with?',
                isFinal: true,
            })
            room.cb.onSegment({ id: 's2', speaker: 'user', text: 'This is Asha', isFinal: true })
        })
        expect(screen.getByTestId('sphere')).toHaveAttribute('data-mode', 'speaking')
        const log = screen.getByRole('log', { name: 'Conversation transcript' })
        expect([...log.querySelectorAll('.bubble p')].map((p) => p.textContent)).toEqual([
            'Hello, who am I speaking with?',
            'This is Asha',
        ])
        act(() => room.cb.onAgentState('listening'))
        expect(screen.getByTestId('sphere')).toHaveAttribute('data-mode', 'listening')

        // end the call: the summary column opens, then fills in once the agent has written it
        await userEvent.click(screen.getByRole('button', { name: 'End call' }))
        expect(seen.some((c) => c.key === 'POST /calls/c1/end')).toBe(true)
        expect(screen.getByTestId('sphere')).toHaveAttribute('data-mode', 'idle')
        const panel = await screen.findByRole('complementary', { name: 'Call summary' })
        expect(within(panel).getByText(/Generating summary/)).toBeInTheDocument()
        summaryReady = true
        expect(
            await within(panel).findByText('Asha agreed to pay', {}, { timeout: 4000 }),
        ).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Back to Your Agent' })).toHaveAttribute('href', '/agent/u1')
    })

    it('shows the server error in the pop-up and lets the user try again', async () => {
        backend(AGENT, {
            'POST /users/u1/collections/calls': () =>
                json({ error: { message: 'Create your agent before placing calls.' } }, 409),
        })
        renderAt('/agent/u1')
        const dialog = await openIndividual()
        await userEvent.type(within(dialog).getByLabelText('Client name'), 'Asha Rao')
        fireEvent.change(within(dialog).getByLabelText('Payment deadline'), {
            target: { value: '2026-11-30' },
        })
        await userEvent.type(within(dialog).getByLabelText('Phone number'), '+919812345678')
        await userEvent.type(within(dialog).getByLabelText('Pending amount'), '500')
        await userEvent.type(within(dialog).getByLabelText('Call context'), 'Context')
        await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm Call' }))
        expect(await within(dialog).findByRole('alert')).toHaveTextContent('Create your agent')
        expect(within(dialog).getByRole('button', { name: 'Confirm Call' })).toBeEnabled()
        expect(room.joined).toHaveLength(0)
    })

    it('the Call Page without a call says so and links back', async () => {
        backend()
        renderAt('/call/u1')
        expect(await screen.findByText(/No call is in progress/)).toBeInTheDocument()
        expect(screen.getByRole('link', { name: 'Back to Your Agent' })).toHaveAttribute('href', '/agent/u1')
    })
})

describe('bulk call', () => {
    const RESULT = (valid, invalid = 0) => ({
        total: valid + invalid,
        valid,
        invalid,
        ignored_columns: [],
        rows: [],
    })
    const openBulk = async () => {
        await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: /Bulk Call/ }))
        return screen.getByRole('dialog')
    }

    it('with no CSV uploaded: a red error, guidance to the Bulk Calling page, and Return closes it', async () => {
        backend()
        renderAt('/agent/u1')
        const dialog = await openBulk()
        expect(dialog).toHaveAccessibleName('No CSV file to call')
        expect(within(dialog).getByRole('alert')).toHaveTextContent('There is no CSV file in the queue yet.')
        expect(within(dialog).getByRole('alert')).toHaveClass('field-error')
        expect(within(dialog).getByRole('link', { name: 'Bulk Calling' })).toHaveAttribute(
            'href',
            '/bulk-calling/u1',
        )
        expect(
            within(dialog)
                .getAllByRole('button')
                .map((b) => b.textContent),
        ).toEqual(['Return'])
        await userEvent.click(within(dialog).getByRole('button', { name: 'Return' }))
        expect(screen.queryByRole('dialog')).toBeNull()
        expect(screen.getByRole('button', { name: /^Ava, Free/ })).toBeInTheDocument()
    })

    it('a file with no ready rows counts as an empty queue', async () => {
        backend()
        const store = makeStore()
        store.dispatch(csvUploaded({ fileName: 'bad.csv', uploadedAt: 't', result: RESULT(0, 3) }))
        renderAt('/agent/u1', store)
        const dialog = await openBulk()
        expect(within(dialog).getByRole('alert')).toHaveTextContent('no rows that are ready')
    })

    it('uses the file uploaded on the Bulk Calling page; Proceed places no calls, Cancel closes', async () => {
        const seen = backend(
            { ...AGENT, voice: 'female' },
            {
                'POST /users/u1/bulk-calls/preview': () => json(RESULT(2, 1)),
            },
        )
        const { router } = renderAt('/bulk-calling/u1')
        await userEvent.upload(
            await screen.findByLabelText('CSV file of people to call'),
            new File(['name,phone\n'], 'october.csv', { type: 'text/csv' }),
        )
        await screen.findByRole('region', { name: 'Borrowers in the file' })
        await act(() => router.navigate('/agent/u1'))
        const dialog = await openBulk()
        expect(dialog).toHaveAccessibleName('Bulk Call')
        expect(within(dialog).getByText('october.csv')).toBeInTheDocument()
        expect(within(dialog).getByText(/2 people ready · 1 with errors/)).toBeInTheDocument()
        expect(within(dialog).getByText('The agent will speak in its female voice.')).toBeInTheDocument()
        const before = seen.length
        await userEvent.click(within(dialog).getByRole('button', { name: 'Proceed with the bulk call' }))
        expect(within(dialog).getByRole('status')).toHaveTextContent('no calls were placed')
        expect(seen.slice(before).filter((c) => c.req.method !== 'GET')).toHaveLength(0) // nothing was sent
        expect(room.joined).toHaveLength(0)
        await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
        expect(screen.queryByRole('dialog')).toBeNull()

        await openBulk()
        await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }))
        expect(screen.queryByRole('dialog')).toBeNull()

        // the upload is still on the Bulk Calling page when the user goes back
        await act(() => router.navigate('/bulk-calling/u1'))
        expect(await screen.findByText('october.csv')).toBeInTheDocument()
    })
})

describe('dashboard while a call is live', () => {
    it('shows "Live · mm:ss · Return to call" and "Start a call" leads back to the call', async () => {
        backend(AGENT, {
            'GET /users/u1/dashboard': () =>
                json({
                    tz: 'UTC',
                    today: '2026-11-18',
                    calls_today: 1,
                    promises: { promised: 0, of: 0 },
                    reply_seconds: null,
                    replies: 0,
                    need_person: 0,
                    recent_calls: [],
                    next_actions: [],
                }),
            'GET /users/u1/stats/calls-per-day': () =>
                json({
                    tz: 'UTC',
                    today: '2026-11-18',
                    days: [{ date: '2026-11-18', weekday: 'Wed', calls: 1 }],
                }),
        })
        const store = makeStore()
        store.dispatch(statusChanged('connected'))
        renderAt('/dashboard/u1', store)
        const pill = await screen.findByRole('link', { name: /Return to call/ })
        expect(pill).toHaveAttribute('href', '/call/u1')
        expect(pill).toHaveTextContent(/Live · 00:0\d/)
        expect(await screen.findByText('Ava is on a call.')).toBeInTheDocument()
        expect(screen.getAllByRole('link', { name: 'Return to call' }).at(-1)).toHaveAttribute(
            'href',
            '/call/u1',
        )
        const nav = screen.getByRole('navigation', { name: 'Main' })
        expect(within(nav).getByText('In a call')).toBeInTheDocument()
    })
})

describe('phone calls (once the Twilio trunk is set up)', () => {
    const phoneOn = { 'GET /auth/config': () => json({ google: false, phone_calls: true }) }
    const RESULT = (valid, invalid = 0) => ({
        total: valid + invalid,
        valid,
        invalid,
        ignored_columns: [],
        rows: [],
    })
    const openBulk = async () => {
        await userEvent.click(within(await openMenu()).getByRole('menuitem', { name: /Bulk Call/ }))
        return screen.getByRole('dialog')
    }
    const fill = async (dialog) => {
        await userEvent.type(within(dialog).getByLabelText('Client name'), 'Asha Rao')
        fireEvent.change(within(dialog).getByLabelText('Payment deadline'), {
            target: { value: '2026-11-30' },
        })
        await userEvent.type(within(dialog).getByLabelText('Phone number'), '+91 98123 45678')
        await userEvent.type(within(dialog).getByLabelText('Pending amount'), '12000')
        await userEvent.type(within(dialog).getByLabelText('Call context'), 'Asha Rao')
    }

    it('without the trunk there is no choice: every call is a browser call', async () => {
        backend()
        renderAt('/agent/u1')
        const dialog = await openIndividual()
        expect(within(dialog).queryByRole('radiogroup')).toBeNull()
        expect(within(dialog).getByRole('button', { name: 'Confirm Call' })).toBeInTheDocument()
    })

    it('"Call their phone" dials the borrower and the browser only listens, showing where the phone is', async () => {
        const seen = backend(AGENT, {
            ...phoneOn,
            'POST /users/u1/collections/calls': () =>
                json({ call_id: 'c1', livekit_url: 'wss://lk', token: 'listen-1', mode: 'phone' }),
            'GET /calls/c1': () =>
                json({ id: 'c1', summary_status: 'READY', summary: null, end_reason: 'busy', turns: [] }),
        })
        renderAt('/agent/u1')
        const dialog = await openIndividual()
        const choice = await within(dialog).findByRole('radiogroup', { name: 'How should the agent call?' })
        expect(within(choice).getByRole('radio', { name: 'Call their phone' })).toHaveAttribute(
            'aria-checked',
            'true',
        )
        await fill(dialog)
        await userEvent.click(within(dialog).getByRole('button', { name: 'Call now' }))

        expect((await posts(seen)[0].req.json()).mode).toBe('phone')
        expect(room.opts).toEqual({ listenOnly: true }) // no microphone: the agent talks to the borrower
        expect(await screen.findByRole('heading', { name: 'Phone call' })).toBeInTheDocument()
        act(() => room.cb.onStatus('connected'))
        expect(screen.getByText('Calling the borrower…')).toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Mute' })).toBeNull()
        act(() => room.cb.onPhoneStatus('ringing'))
        expect(screen.getByText('Ringing…')).toBeInTheDocument()
        act(() => room.cb.onPhoneStatus('active'))
        expect(screen.getByText('On the phone')).toBeInTheDocument()

        // the borrower did not pick up: the agent ends the call and the page says why
        act(() => room.cb.onDisconnected())
        expect(await screen.findByText('The call did not connect: Busy.')).toBeInTheDocument()
    })

    it('"Try it in the browser" still makes a browser call', async () => {
        const seen = backend(AGENT, phoneOn)
        renderAt('/agent/u1')
        const dialog = await openIndividual()
        await userEvent.click(await within(dialog).findByRole('radio', { name: 'Try it in the browser' }))
        await fill(dialog)
        await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm Call' }))
        await waitFor(() => expect(posts(seen)).toHaveLength(1))
        expect((await posts(seen)[0].req.json()).mode).toBe('web')
        expect(room.opts).toEqual({ listenOnly: false })
    })

    it('Proceed starts the bulk call with the uploaded file, then shows its progress; Pause is sent', async () => {
        let job = null
        const running = {
            job_id: 'j1',
            status: 'running',
            file_name: 'october.csv',
            total: 2,
            counts: { pending: 1, calling: 1, done: 0, skipped: 0 },
            answered: 0,
            items: [
                { seq: 0, name: 'Asha Rao', phone_last4: '5678', status: 'calling', result: null },
                { seq: 1, name: 'Ravi Kumar', phone_last4: '3210', status: 'pending', result: null },
            ],
        }
        const seen = backend(AGENT, {
            ...phoneOn,
            'POST /users/u1/bulk-calls/preview': () => json(RESULT(2, 0)),
            'GET /users/u1/bulk-calls/current': () => json(job),
            'POST /users/u1/bulk-calls': () => {
                job = running
                return json(running, 201)
            },
            'POST /users/u1/bulk-calls/j1/pause': () => {
                job = { ...running, status: 'paused' }
                return json(job)
            },
        })
        const { router } = renderAt('/bulk-calling/u1')
        await userEvent.upload(
            await screen.findByLabelText('CSV file of people to call'),
            new File(['name,phone,amount,deadline\n'], 'october.csv', { type: 'text/csv' }),
        )
        await screen.findByRole('region', { name: 'Borrowers in the file' })
        await act(() => router.navigate('/agent/u1'))
        const dialog = await openBulk()
        expect(within(dialog).getByText(/phone each person in turn/)).toBeInTheDocument()
        await userEvent.click(within(dialog).getByRole('button', { name: 'Proceed with the bulk call' }))

        const start = seen.find((c) => c.key === 'POST /users/u1/bulk-calls')
        expect(new URL(start.req.url).searchParams.get('file_name')).toBe('october.csv')
        expect(await start.req.text()).toBe('name,phone,amount,deadline\n') // the uploaded bytes
        const list = await within(dialog).findByRole('list', { name: 'People in this bulk call' })
        expect(within(list).getByText('Calling now…')).toBeInTheDocument()
        expect(within(list).getByText('•••• 3210')).toBeInTheDocument()
        expect(within(dialog).getByText('0 of 2 called · 0 answered')).toBeInTheDocument()
        await userEvent.click(within(dialog).getByRole('button', { name: 'Pause' }))
        expect(seen.some((c) => c.key === 'POST /users/u1/bulk-calls/j1/pause')).toBe(true)
        expect(await within(dialog).findByRole('button', { name: 'Resume' })).toBeInTheDocument()
    })
})
