import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { makeStore } from '../app/store'
import RolePage from './RolePage'

const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })

function renderPage() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <RolePage />
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

it('shows the heading and hides "use last time" when there is no active profile', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => json({ error: { message: 'none' } }, 404)),
  )
  renderPage()
  expect(screen.getByRole('heading', { name: /role and behaviour of the agent/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  await new Promise((r) => setTimeout(r, 50))
  expect(screen.queryByText(/from last time/i)).not.toBeInTheDocument()
})

it('offers "use last time" with a preview when a profile exists', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      json({
        profile_id: 'p',
        version: 1,
        context_prompt: 'x'.repeat(30),
        structured_fields: { role_summary: 'Dental receptionist' },
        placeholders: [],
        assumptions_made: [],
      }),
    ),
  )
  renderPage()
  expect(await screen.findByRole('button', { name: /from last time/i })).toBeInTheDocument()
  expect(screen.getByText(/Dental receptionist/)).toBeInTheDocument()
})

it('shows an error with retry when generation fails', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request) =>
      req.url.includes('generate')
        ? json({ error: { message: 'The language model is unavailable right now. Please retry.' } }, 502)
        : json({}, 404),
    ),
  )
  renderPage()
  await userEvent.type(screen.getByLabelText(/agent role/i), 'A friendly dental receptionist')
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable/i)
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
})

it('shows progress while generating and lets the user cancel', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((req: Request) => {
      if (!req.url.includes('generate')) return Promise.resolve(json({}, 404))
      return new Promise((_res, rej) =>
        req.signal.addEventListener('abort', () => rej(new DOMException('Aborted', 'AbortError'))),
      )
    }),
  )
  renderPage()
  await userEvent.type(screen.getByLabelText(/agent role/i), 'A friendly dental receptionist')
  await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
  expect(await screen.findByRole('status')).toHaveTextContent(/Reading your description/)
  await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  await vi.waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})
