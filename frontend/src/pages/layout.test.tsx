import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { makeStore } from '../app/store'
import Sidebar from '../components/Sidebar/Sidebar'
import { callEnded, callStarting } from '../features/call/slice'
import CallPage from './CallPage'
import ChatPage from './ChatPage'

vi.mock('../components/Sphere/Sphere', () => ({
  default: () => <div data-testid="sphere" />,
  sphereMode: () => 'idle',
}))
vi.mock('../features/call/CallProvider', () => ({
  useCall: () => ({
    manager: { getLevels: () => ({ user: 0, agent: 0 }) },
    start: vi.fn(),
    end: vi.fn(),
    setMuted: vi.fn(),
  }),
}))

const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { 'content-type': 'application/json' } })
const SUMMARY = {
  title: 'Room inquiry',
  summary: 'Caller asked about rooms.',
  call_outcome: 'completed',
  key_points: ['Asked about rooms'],
  user_requests: [],
  agent_commitments_and_next_actions: [],
  unresolved_items: [],
  information_collected: {},
  sentiment: 'neutral',
  escalation_needed: false,
  escalation_reason: null,
  topics_outside_scope_raised: [],
  confidence_notes: '',
}
const CALL = {
  id: 'c1',
  title: 'Room inquiry',
  status: 'COMPLETED',
  summary_status: 'READY',
  started_at: null,
  ended_at: null,
  end_reason: null,
  turns: [{ seq: 0, speaker: 'agent', text: 'Hello there', is_final: true }],
  summary: SUMMARY,
}

afterEach(() => vi.unstubAllGlobals())

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>
}

it('"New call" always returns to the role screen', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => json([])),
  )
  render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/chats/c1']}>
        <Sidebar />
        <Where />
      </MemoryRouter>
    </Provider>,
  )
  await userEvent.click(screen.getByRole('button', { name: /new call/i }))
  expect(screen.getByTestId('where')).toHaveTextContent(/^\/$/)
})

it('past call: chat in the main column, summary in the right-hand panel', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => json(CALL)),
  )
  render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/chats/c1']}>
        <Routes>
          <Route path="/chats/:id" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
  const panel = await screen.findByRole('complementary', { name: /call summary/i })
  expect(within(panel).getByText('Caller asked about rooms.')).toBeInTheDocument()
  expect(screen.getByText('Hello there').closest('.call-main')).not.toBeNull()
  expect(panel.closest('.call-main')).toBeNull() // a sibling column, not nested under the chat
})

it('the summary panel opens as soon as the call ends and fills in when ready', async () => {
  let ready = false
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request) =>
      req.url.includes('/calls/c1')
        ? json(ready ? CALL : { ...CALL, summary: null, summary_status: 'PENDING' })
        : json({}, 404),
    ),
  )
  const store = makeStore()
  render(
    <Provider store={store}>
      <MemoryRouter>
        <CallPage />
      </MemoryRouter>
    </Provider>,
  )
  expect(screen.queryByRole('complementary')).not.toBeInTheDocument() // live call: chat uses the full width
  store.dispatch(callStarting('c1'))
  store.dispatch(callEnded('c1'))
  expect(await screen.findByText(/Generating summary/)).toBeInTheDocument()
  ready = true
  expect(await screen.findByText('Caller asked about rooms.', {}, { timeout: 6000 })).toBeInTheDocument()
}, 12000)
