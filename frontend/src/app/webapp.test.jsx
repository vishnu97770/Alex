import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { makeStore } from './store'
import { routes } from './router'

vi.mock('../features/call/CallProvider', () => ({
    CallProvider: ({ children }) => children,
    useCall: () => ({
        manager: { getLevels: () => ({ user: 0, agent: 0 }) },
        start: vi.fn(),
        end: vi.fn(),
        setMuted: vi.fn(),
    }),
}))
vi.mock('../pages/Landing', () => ({ default: () => <div data-testid="landing" /> }))
vi.mock('../components/Sphere/Sphere', () => ({
    default: () => <div data-testid="sphere" />,
    sphereMode: () => 'idle',
}))

const ME = { uid: 'u1', username: 'Ann', email: 'ann@example.com', avatar_url: null, agent_count: 1 }
const json = (b, status = 200) =>
    new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })

/** Routes a fake backend by "METHOD /path"; unknown -> 404. */
function mockApi(handlers) {
    const calls = []
    vi.stubGlobal(
        'fetch',
        vi.fn(async (req) => {
            const path = new URL(req.url).pathname.replace('/api/v1', '')
            const key = `${req.method} ${path}`
            calls.push({ key, req })
            const h = handlers[key]
            return h ? h(req) : json({ error: { message: 'nope' } }, 404)
        }),
    )
    return calls
}

function renderAt(path) {
    const router = createMemoryRouter(routes, { initialEntries: [path] })
    render(
        <Provider store={makeStore()}>
            <RouterProvider router={router} />
        </Provider>,
    )
    return router
}

const signedIn = { 'GET /auth/me': () => json(ME) }
const signedOut = { 'GET /auth/me': () => json({ error: { message: 'Not authenticated' } }, 401) }

afterEach(() => vi.unstubAllGlobals())

describe('route guard', () => {
    it('/home shows the landing page even when signed in (its nav offers "Open app")', async () => {
        mockApi({ ...signedIn })
        const router = renderAt('/home')
        expect(await screen.findByTestId('landing')).toBeInTheDocument()
        expect(router.state.location.pathname).toBe('/home')
    })

    it('/home without a valid token shows the landing page', async () => {
        mockApi({ ...signedOut, 'GET /auth/config': () => json({ google: false }) })
        const router = renderAt('/home')
        expect(await screen.findByTestId('landing')).toBeInTheDocument()
        expect(router.state.location.pathname).toBe('/home')
    })

    it('a protected page without a token goes to /checkin', async () => {
        mockApi({ ...signedOut, 'GET /auth/config': () => json({ google: false }) })
        const router = renderAt('/agents/u1')
        await waitFor(() => expect(router.state.location.pathname).toBe('/checkin'))
    })

    it("someone else's uid in the URL is sent to your own dashboard", async () => {
        mockApi(signedIn)
        const router = renderAt('/profile/other-user')
        await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard/u1'))
    })
})

describe('shared navbar', () => {
    it.each(['dashboard', 'agents', 'manager', 'profile', 'settings'])(
        '%s page has the five links in order',
        async (page) => {
            mockApi({
                ...signedIn,
                'GET /users/u1/agents': () => json([]),
                'GET /users/u1/manager/calls': () => json([]),
                'GET /agent-profiles/active': () => json({}, 404),
            })
            renderAt(`/${page}/u1`)
            const nav = await screen.findByRole('navigation', { name: 'Main' })
            const links = Array.from(nav.querySelectorAll('a'))
            expect(links.map((a) => a.textContent)).toEqual([
                'My Dashboard',
                'My Agents',
                'My Manager',
                'My Profile',
                'Settings',
            ])
            expect(links.map((a) => a.getAttribute('href'))).toEqual([
                '/dashboard/u1',
                '/agents/u1',
                '/manager/u1',
                '/profile/u1',
                '/settings/u1',
            ])
        },
    )
})

describe('dashboard and agents', () => {
    it('profile icon opens the profile page', async () => {
        mockApi({ ...signedIn })
        const router = renderAt('/dashboard/u1')
        await userEvent.click(await screen.findByRole('button', { name: /open your profile/i }))
        expect(router.state.location.pathname).toBe('/profile/u1')
    })

    it('lists agents with status and goes to create / update pages', async () => {
        mockApi({
            ...signedIn,
            'GET /users/u1/agents': () =>
                json([
                    { aid: 'a1', name: 'Ava', role_behavior: 'x', status: 'free', lifecycle: 'ACTIVE' },
                    { aid: 'a2', name: 'Ben', role_behavior: 'y', status: 'busy', lifecycle: 'ACTIVE' },
                ]),
        })
        const router = renderAt('/agents/u1')
        expect(await screen.findByText('Ann’s agents')).toBeInTheDocument()
        expect(await screen.findByText('Ava')).toBeInTheDocument()
        expect(
            screen.getAllByRole('img', { name: /free|busy/i }).map((e) => e.getAttribute('aria-label')),
        ).toEqual(['Free', 'Busy'])
        await userEvent.click(screen.getByRole('button', { name: 'Edit Ben' }))
        expect(router.state.location.pathname).toBe('/agents/u1/update/a2')
        router.navigate('/agents/u1')
        await userEvent.click(await screen.findByRole('button', { name: /create new agent/i }))
        expect(router.state.location.pathname).toBe('/create_agent/u1')
    })

    it('create agent -> payment of 100 -> back to the agents list', async () => {
        let paid = null
        mockApi({
            ...signedIn,
            'POST /users/u1/agents': () => json({ aid: 'a9', name: 'Zed', lifecycle: 'PENDING' }, 201),
            'POST /users/u1/agents/a9/payment': async (req) => {
                paid = await req.json()
                return json({ aid: 'a9', name: 'Zed', lifecycle: 'ACTIVE' })
            },
            'GET /users/u1/agents': () => json([]),
        })
        const router = renderAt('/create_agent/u1')
        await userEvent.type(await screen.findByLabelText(/agent’s name/i), 'Zed')
        await userEvent.type(
            screen.getByLabelText(/role and behaviour/i),
            'Answers support questions politely',
        )
        await userEvent.click(screen.getByRole('button', { name: 'Create agent' }))
        await waitFor(() => expect(router.state.location.pathname).toBe('/create_agent/u1/a9'))
        await userEvent.type(await screen.findByLabelText('Enter amount'), '100')
        await userEvent.click(screen.getByRole('button', { name: 'Pay' }))
        await waitFor(() => expect(router.state.location.pathname).toBe('/agents/u1'))
        expect(paid).toEqual({ amount: '100' })
    })

    it('shows the error and stays on the payment page when the amount is wrong', async () => {
        mockApi({
            ...signedIn,
            'POST /users/u1/agents/a9/payment': () =>
                json(
                    {
                        error: {
                            code: 'payment_rejected',
                            message: 'Payment failed: please enter the exact amount (100).',
                        },
                    },
                    402,
                ),
        })
        const router = renderAt('/create_agent/u1/a9')
        await userEvent.type(await screen.findByLabelText('Enter amount'), '5')
        await userEvent.click(screen.getByRole('button', { name: 'Pay' }))
        expect(await screen.findByRole('alert')).toHaveTextContent(/exact amount/i)
        expect(router.state.location.pathname).toBe('/create_agent/u1/a9')
    })

    it('update page is prefilled and Save returns to the list', async () => {
        let saved = null
        mockApi({
            ...signedIn,
            'GET /users/u1/agents/a1': () =>
                json({
                    aid: 'a1',
                    name: 'Ava',
                    role_behavior: 'Books appointments',
                    status: 'free',
                    lifecycle: 'ACTIVE',
                }),
            'PUT /users/u1/agents/a1': async (req) => {
                saved = await req.json()
                return json({
                    aid: 'a1',
                    name: 'Ava 2',
                    role_behavior: saved.role_behavior,
                    status: 'free',
                    lifecycle: 'ACTIVE',
                })
            },
            'GET /users/u1/agents': () => json([]),
        })
        const router = renderAt('/agents/u1/update/a1')
        const name = await screen.findByLabelText('Update Agent name')
        await waitFor(() => expect(name).toHaveValue('Ava'))
        expect(screen.getByLabelText(/update role and behaviour/i)).toHaveValue('Books appointments')
        await userEvent.clear(name)
        await userEvent.type(name, 'Ava 2')
        await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
        await waitFor(() => expect(router.state.location.pathname).toBe('/agents/u1'))
        expect(saved.name).toBe('Ava 2')
    })
})

describe('manager, profile, settings, checkin', () => {
    it('manager page: calls bar highlights the open call and shows transcript + summary', async () => {
        mockApi({
            ...signedIn,
            'GET /users/u1/manager/calls': () =>
                json([
                    {
                        id: 'c1',
                        title: 'Busy agents',
                        status: 'COMPLETED',
                        summary_status: 'READY',
                        started_at: null,
                    },
                ]),
            'GET /calls/c1': () =>
                json({
                    id: 'c1',
                    title: 'Busy agents',
                    summary_status: 'READY',
                    turns: [{ seq: 0, speaker: 'agent', text: 'Ava is free', is_final: true }],
                    summary: {
                        title: 'Busy agents',
                        summary: 'Asked who is busy.',
                        call_outcome: 'completed',
                        key_points: [],
                        user_requests: [],
                        agent_commitments_and_next_actions: [],
                        unresolved_items: [],
                        information_collected: {},
                        sentiment: 'neutral',
                        escalation_needed: false,
                        escalation_reason: null,
                        topics_outside_scope_raised: [],
                        confidence_notes: '',
                    },
                }),
        })
        renderAt('/manager/u1')
        const link = await screen.findByRole('link', { name: 'Busy agents' })
        await userEvent.click(link)
        expect(await screen.findByText('Ava is free')).toBeInTheDocument()
        expect(await screen.findByRole('complementary', { name: /call summary/i })).toBeInTheDocument()
        await waitFor(() => expect(screen.getByRole('link', { name: 'Busy agents' })).toHaveClass('active'))
    })

    it('profile page shows the details and logout goes to /checkin', async () => {
        let authed = true
        mockApi({
            'GET /auth/me': () => (authed ? json(ME) : json({ error: { message: 'no' } }, 401)),
            'POST /auth/logout': () => {
                authed = false
                return json({ status: 'logged_out' })
            },
            'GET /auth/config': () => json({ google: true }),
        })
        const router = renderAt('/profile/u1')
        expect(await screen.findByText('ann@example.com')).toBeInTheDocument()
        expect(screen.getByText('Ann')).toBeInTheDocument()
        expect(screen.getByLabelText('Upload profile picture')).toBeInTheDocument()
        await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
        await waitFor(() => expect(router.state.location.pathname).toBe('/checkin'))
    })

    it('settings toggles the theme', async () => {
        mockApi(signedIn)
        renderAt('/settings/u1')
        const toggle = await screen.findByRole('switch', { name: 'Theme' })
        const before = toggle.getAttribute('aria-checked')
        await userEvent.click(toggle)
        expect(toggle.getAttribute('aria-checked')).not.toBe(before)
        expect(document.documentElement.dataset.theme).toBe(before === 'true' ? 'light' : 'dark')
    })

    it('checkin: email sign-in goes to the dashboard; Google is disabled when not configured', async () => {
        let authed = false
        mockApi({
            'GET /auth/me': () => (authed ? json(ME) : json({ error: { message: 'no' } }, 401)),
            'GET /auth/config': () => json({ google: false }),
            'POST /auth/login': () => {
                authed = true
                return json(ME)
            },
            'GET /users/u1/agents': () => json([]),
        })
        const router = renderAt('/checkin')
        expect(await screen.findByText('Continue with Google')).toHaveAttribute('aria-disabled', 'true')
        await userEvent.type(screen.getByLabelText('Email'), 'ann@example.com')
        await userEvent.type(screen.getByLabelText('Password'), 'correct-horse-1')
        await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
        await waitFor(() => expect(router.state.location.pathname).toBe('/dashboard/u1'))
    })

    it('checkin shows the server error for bad credentials', async () => {
        mockApi({
            ...signedOut,
            'GET /auth/config': () => json({ google: true }),
            'POST /auth/login': () => json({ error: { message: 'Incorrect email or password' } }, 401),
        })
        renderAt('/checkin')
        await userEvent.type(await screen.findByLabelText('Email'), 'a@b.co')
        await userEvent.type(screen.getByLabelText('Password'), 'wrongwrong')
        await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
    })

    it('checkin stays on the sign-in form for a signed-in visitor, with a way back to the dashboard', async () => {
        mockApi({ ...signedIn, 'GET /auth/config': () => json({ google: false }) })
        const router = renderAt('/checkin')
        expect(await screen.findByLabelText('Email')).toBeInTheDocument()
        expect(await screen.findByRole('link', { name: /continue to your dashboard/i })).toHaveAttribute(
            'href',
            '/dashboard/u1',
        )
        expect(router.state.location.pathname).toBe('/checkin')
    })
})
