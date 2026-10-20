import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { makeStore } from '../../app/store'
import CallToAction from './sections/CallToAction'
import Nav from './Nav'

vi.mock('./stage/OrbAnchor.jsx', () => ({ default: () => null }))

const json = (b, status = 200) =>
    new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })

function Where() {
    const l = useLocation()
    return <div data-testid="where">{l.pathname + l.search}</div>
}

function renderAt(ui, me = null) {
    vi.stubGlobal(
        'fetch',
        vi.fn(async () => (me ? json(me) : json({ error: { message: 'no' } }, 401))),
    )
    return render(
        <Provider store={makeStore()}>
            <MemoryRouter initialEntries={['/home']}>
                <Routes>
                    <Route path="/home" element={ui} />
                    <Route path="*" element={<Where />} />
                </Routes>
            </MemoryRouter>
        </Provider>,
    )
}

afterEach(() => vi.unstubAllGlobals())

it('Nav "Sign in" goes to /checkin', async () => {
    renderAt(<Nav />)
    const [signIn] = screen.getAllByRole('link', { name: 'Sign in' })
    await userEvent.click(signIn)
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/checkin$/)
})

it('Nav "Sign up" goes to /checkin (on the create-account form)', async () => {
    renderAt(<Nav />)
    const [signUp] = screen.getAllByRole('link', { name: /^Sign up/ })
    await userEvent.click(signUp)
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/checkin\?mode=register$/)
})

it('"Get started" and the call-to-action links go to /checkin', async () => {
    renderAt(<CallToAction />)
    await userEvent.click(screen.getByRole('link', { name: /get started/i }))
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/checkin/)
})

it('a signed-in visitor is offered "Open app" instead of Sign in', async () => {
    renderAt(<Nav />, { uid: 'u1', username: 'Ann', email: 'a@b.co', avatar_url: null, agent_count: 0 })
    const open = await screen.findAllByRole('link', { name: /open app/i })
    expect(open[0]).toHaveAttribute('href', '/dashboard/u1')
})
