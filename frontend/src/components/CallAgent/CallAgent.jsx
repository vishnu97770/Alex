import { useEffect, useId, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
    errorMessage,
    useAuthConfigQuery,
    useControlBulkCallMutation,
    useGetBulkCallQuery,
    useStartBulkCallMutation,
} from '../../api/api'
import { useAppSelector } from '../../app/hooks'
import { csvFileFor } from '../../features/bulk/files'
import { selectCsvFiles, selectReadyCsvFiles } from '../../features/bulk/slice'
import { useCall } from '../../features/call/CallProvider'
import { NOT_CONNECTED } from '../../lib/callOutcome'
import { formatAmount } from '../../lib/money'
import { voiceLabel } from '../../lib/voice'
import { LIVE } from '../CallControls/CallControls'
import Modal, { useModalClose } from '../Modal/Modal'

// The server applies the same rules (SoloCallIn); these only give instant feedback.
export const CONTEXT_MAX = 4000
const MAX_AMOUNT = 1_000_000_000
const CURRENCY = 'INR'

/** Digits with an optional leading +, 10 to 15 digits, after removing spaces, dashes, dots and brackets. */
export function normalizePhone(raw) {
    const p = raw.replace(/[\s().-]/g, '')
    return /^\+?[1-9]\d{9,14}$/.test(p) ? p : null
}

/** "12,000.50", "₹ 12000" -> "12000.50"; null when not a positive amount with at most 2 decimals. */
export function normalizeAmount(raw) {
    const t = raw.replace(/[₹,\s]/g, '').replace(/^(rs\.?|inr)/i, '')
    if (!/^\d+(\.\d{1,2})?$/.test(t)) return null
    const n = Number(t)
    if (!(n > 0) || n > MAX_AMOUNT) return null
    return n.toFixed(2)
}

/** Field errors for the Individual Call form (empty object when it is valid). */
export function checkCallForm({ name, phone, amount, deadline, context }) {
    const errors = {}
    if (!name.trim()) errors.name = 'Enter the client’s name.'
    else if (name.trim().length < 2) errors.name = 'Enter the client’s full name.'
    if (!phone.trim()) errors.phone = 'Enter the client’s phone number.'
    else if (!normalizePhone(phone))
        errors.phone =
            'Enter a valid phone number: 10 to 15 digits, with the country code (e.g. +91 98765 43210).'
    if (!amount.trim()) errors.amount = 'Enter the pending amount.'
    else if (!normalizeAmount(amount))
        errors.amount = 'Enter an amount greater than zero, with at most 2 decimal places.'
    if (!deadline) errors.deadline = 'Choose the payment deadline.'
    if (!context.trim()) errors.context = 'Add some context about the client and their loan.'
    else if (context.length > CONTEXT_MAX)
        errors.context = `Keep the context under ${CONTEXT_MAX} characters.`
    return errors
}

const CONTEXT_HINT = [
    'For example:',
    '• Lender and loan reference',
    '• Original loan amount and what is still pending',
    '• Past repayments and missed payments',
    '• Earlier calls or messages, and anything else the agent should know',
].join('\n')

function Field({ id, label, error, hint, children }) {
    return (
        <div className="call-field">
            <label htmlFor={id}>{label}</label>
            {children}
            {hint && !error && (
                <span className="muted field-hint" id={`${id}-hint`}>
                    {hint}
                </span>
            )}
            {error && (
                <span className="field-error" id={`${id}-error`}>
                    {error}
                </span>
            )}
        </div>
    )
}

/** Which of the agent's voices its calls will use (chosen when the agent was created). */
function VoiceNote({ voice }) {
    const label = voiceLabel(voice)
    return label ? <p className="muted">The agent will speak in its {label.toLowerCase()} voice.</p> : null
}

// How an individual call is made, once phone calls are set up (until then every call is a browser call).
const CALL_MODES = [
    {
        value: 'phone',
        label: 'Call their phone',
        hint: 'The agent rings this number. You can listen in here.',
    },
    {
        value: 'web',
        label: 'Try it in the browser',
        hint: 'You play the client yourself, with your microphone.',
    },
]

function IndividualCallForm({ onStarted, onBusyChange, voice }) {
    const close = useModalClose()
    const { start } = useCall()
    const phoneCalls = useAuthConfigQuery().data?.phone_calls === true
    const [mode, setMode] = useState('phone')
    const [form, setForm] = useState({ name: '', phone: '', amount: '', deadline: '', context: '' })
    const [touched, setTouched] = useState({})
    const [submitted, setSubmitted] = useState(false)
    const [busy, setBusy] = useState(false)
    const [serverError, setServerError] = useState(null)
    const inFlight = useRef(false) // set synchronously: a double click cannot start two calls
    const ids = {
        name: useId(),
        phone: useId(),
        amount: useId(),
        deadline: useId(),
        context: useId(),
        mode: useId(),
    }
    const errors = checkCallForm(form)
    const shown = (f) => (submitted || touched[f] ? errors[f] : undefined)
    const amount = normalizeAmount(form.amount)
    const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))
    const blur = (f) => () => setTouched((t) => ({ ...t, [f]: true }))
    const describedBy = (f, hint) => (shown(f) ? `${ids[f]}-error` : hint ? `${ids[f]}-hint` : undefined)

    const submit = async (e) => {
        e.preventDefault()
        setSubmitted(true)
        setServerError(null)
        if (Object.keys(errors).length > 0 || inFlight.current) return
        inFlight.current = true
        setBusy(true)
        onBusyChange(true)
        try {
            const id = await start({
                borrower_name: form.name.trim(),
                phone: normalizePhone(form.phone),
                amount,
                currency: CURRENCY,
                due_date: form.deadline,
                context: form.context.trim(),
                mode: phoneCalls ? mode : 'web',
            })
            if (id === null) throw new Error('busy')
            onStarted()
        } catch (err) {
            setServerError(
                err?.message === 'busy'
                    ? 'A call is already in progress.'
                    : errorMessage(err, 'Could not start the call. Please try again.'),
            )
            inFlight.current = false
            setBusy(false)
            onBusyChange(false)
        }
    }

    return (
        <form className="modal-form" noValidate onSubmit={(e) => void submit(e)}>
            <p className="muted modal-lead">
                Your agent will speak as if it is calling this client, using the details below.
            </p>
            <VoiceNote voice={voice} />
            {serverError && (
                <div className="banner error" role="alert">
                    {serverError}
                </div>
            )}
            <Field
                id={ids.name}
                label="Client name"
                error={shown('name')}
                hint="The agent opens with “Am I speaking with …?”"
            >
                <input
                    id={ids.name}
                    type="text"
                    autoComplete="off"
                    placeholder="Asha Rao"
                    value={form.name}
                    onChange={set('name')}
                    onBlur={blur('name')}
                    maxLength={80}
                    required
                    aria-invalid={!!shown('name')}
                    aria-describedby={describedBy('name', true)}
                    disabled={busy}
                />
            </Field>
            <Field id={ids.phone} label="Phone number" error={shown('phone')} hint="With the country code">
                <input
                    id={ids.phone}
                    type="tel"
                    inputMode="tel"
                    autoComplete="off"
                    placeholder="+91 98765 43210"
                    value={form.phone}
                    onChange={set('phone')}
                    onBlur={blur('phone')}
                    maxLength={20}
                    required
                    aria-invalid={!!shown('phone')}
                    aria-describedby={describedBy('phone', true)}
                    disabled={busy}
                />
            </Field>
            <Field
                id={ids.amount}
                label="Pending amount"
                error={shown('amount')}
                hint={amount ? formatAmount(amount, CURRENCY) : 'In Indian rupees (INR)'}
            >
                <div className="input-affix">
                    <span aria-hidden>₹</span>
                    <input
                        id={ids.amount}
                        type="text"
                        inputMode="decimal"
                        autoComplete="off"
                        placeholder="12,000"
                        value={form.amount}
                        onChange={set('amount')}
                        onBlur={blur('amount')}
                        maxLength={20}
                        required
                        aria-invalid={!!shown('amount')}
                        aria-describedby={describedBy('amount', true)}
                        disabled={busy}
                    />
                </div>
            </Field>
            <Field
                id={ids.deadline}
                label="Payment deadline"
                error={shown('deadline')}
                hint="The agent does not agree to pay after this date"
            >
                <input
                    id={ids.deadline}
                    type="date"
                    value={form.deadline}
                    onChange={set('deadline')}
                    onBlur={blur('deadline')}
                    required
                    aria-invalid={!!shown('deadline')}
                    aria-describedby={describedBy('deadline', true)}
                    disabled={busy}
                />
            </Field>
            <Field
                id={ids.context}
                label="Call context"
                error={shown('context')}
                hint={`${form.context.length.toLocaleString()} / ${CONTEXT_MAX.toLocaleString()}`}
            >
                <textarea
                    id={ids.context}
                    rows={7}
                    placeholder={CONTEXT_HINT}
                    value={form.context}
                    onChange={set('context')}
                    onBlur={blur('context')}
                    maxLength={CONTEXT_MAX}
                    required
                    aria-invalid={!!shown('context')}
                    aria-describedby={describedBy('context', true)}
                    disabled={busy}
                />
            </Field>
            {phoneCalls && (
                <div className="voice-field">
                    <span id={ids.mode}>How should the agent call?</span>
                    <div role="radiogroup" aria-labelledby={ids.mode} className="swatch-row">
                        {CALL_MODES.map((m) => (
                            <button
                                key={m.value}
                                type="button"
                                role="radio"
                                aria-checked={mode === m.value}
                                onClick={() => setMode(m.value)}
                                disabled={busy}
                            >
                                {m.label}
                            </button>
                        ))}
                    </div>
                    <span className="muted field-hint">{CALL_MODES.find((m) => m.value === mode).hint}</span>
                </div>
            )}
            <div className="box-actions">
                <button type="button" onClick={close} disabled={busy}>
                    Cancel
                </button>
                <button className="primary" disabled={busy}>
                    {busy ? 'Starting call…' : phoneCalls && mode === 'phone' ? 'Call now' : 'Confirm Call'}
                </button>
            </div>
        </form>
    )
}

export function IndividualCallModal({ uid, voice, onClose }) {
    const navigate = useNavigate()
    const [busy, setBusy] = useState(false) // while the call is being created, Escape / backdrop do not close
    return (
        <Modal title="Individual Call" onClose={onClose} busy={busy} className="call-modal">
            <IndividualCallForm
                voice={voice}
                onBusyChange={setBusy}
                onStarted={() => {
                    onClose()
                    navigate(`/call/${uid}`)
                }}
            />
        </Modal>
    )
}

const BULK_POLL_MS = 3000
const BULK_ACTIVE = ['running', 'paused']

function BulkCallModal({ uid, voice, onClose }) {
    const files = useAppSelector(selectCsvFiles)
    const ready = useAppSelector(selectReadyCsvFiles)
    const phoneCalls = useAuthConfigQuery().data?.phone_calls === true
    const [following, setFollowing] = useState(false) // a run started from this pop-up stays shown once it ends
    const { data: job } = useGetBulkCallQuery(uid, {
        skip: !phoneCalls,
        pollingInterval: following ? BULK_POLL_MS : 0,
    })
    const active = !!job && BULK_ACTIVE.includes(job.status)
    useEffect(() => {
        if (active) setFollowing(true)
    }, [active])
    const showProgress = !!job && (active || following)
    const title = showProgress ? 'Bulk Call' : ready.length > 0 ? 'Bulk Call' : 'No CSV file to call'
    return (
        <Modal title={title} onClose={onClose} className="call-modal">
            {showProgress ? (
                <BulkProgress uid={uid} job={job} voice={voice} />
            ) : ready.length > 0 ? (
                <BulkReady
                    uid={uid}
                    files={ready}
                    voice={voice}
                    phoneCalls={phoneCalls}
                    onStarted={() => setFollowing(true)}
                />
            ) : (
                <BulkEmpty uid={uid} hasInvalid={files.length > 0} />
            )}
        </Modal>
    )
}

const ITEM_STATUS = { pending: 'Waiting', calling: 'Calling now…' }
const itemLabel = (i) =>
    ITEM_STATUS[i.status] ??
    (i.status === 'skipped'
        ? 'Skipped'
        : i.result === 'answered'
          ? 'Answered'
          : (NOT_CONNECTED[i.result] ?? 'Done'))

/** A bulk run in progress (or just finished): who is being called, how far it got, and pause / resume / cancel. */
function BulkProgress({ uid, job, voice }) {
    const close = useModalClose()
    const [control, { isLoading }] = useControlBulkCallMutation()
    const [error, setError] = useState(null)
    const called = job.counts.done
    const act = async (action) => {
        setError(null)
        try {
            await control({ uid, jobId: job.job_id, action }).unwrap()
        } catch (err) {
            setError(errorMessage(err, 'Could not change the bulk call. Please try again.'))
        }
    }
    const STATUS = {
        running: 'Calling, one person at a time.',
        paused: 'Paused. The call in progress (if any) finishes; nobody else is called until you resume.',
        cancelled: 'Cancelled. Nobody else will be called.',
        done: 'Finished. Everyone in the file has been called.',
    }
    return (
        <>
            <p role="status">
                <span className="mono">{job.file_name || 'CSV file'}</span>: {STATUS[job.status]}
            </p>
            <p className="muted">
                {called} of {job.total} called · {job.answered} answered
                {job.counts.skipped > 0 ? ` · ${job.counts.skipped} skipped` : ''}
            </p>
            <VoiceNote voice={voice} />
            {error && (
                <div className="banner error" role="alert">
                    {error}
                </div>
            )}
            <ul className="bulk-queue" aria-label="People in this bulk call">
                {job.items.map((i) => (
                    <li key={i.seq}>
                        <span>
                            {i.name} <span className="mono muted">•••• {i.phone_last4}</span>
                        </span>
                        <span className={i.status === 'calling' ? 'strong' : 'muted'}>{itemLabel(i)}</span>
                    </li>
                ))}
            </ul>
            <div className="box-actions">
                <button type="button" onClick={close}>
                    Close
                </button>
                {job.status === 'running' && (
                    <button type="button" onClick={() => void act('pause')} disabled={isLoading}>
                        Pause
                    </button>
                )}
                {job.status === 'paused' && (
                    <button
                        type="button"
                        className="primary"
                        onClick={() => void act('resume')}
                        disabled={isLoading}
                    >
                        Resume
                    </button>
                )}
                {BULK_ACTIVE.includes(job.status) && (
                    <button
                        type="button"
                        className="danger"
                        onClick={() => void act('cancel')}
                        disabled={isLoading}
                    >
                        Cancel bulk call
                    </button>
                )}
            </div>
        </>
    )
}

function BulkEmpty({ uid, hasInvalid }) {
    const close = useModalClose()
    return (
        <>
            <p className="field-error bulk-empty" role="alert">
                {hasInvalid
                    ? 'The uploaded CSV file has no rows that are ready to call.'
                    : 'There is no CSV file in the queue yet.'}
            </p>
            <p className="muted">
                Go to the{' '}
                <Link to={`/bulk-calling/${uid}`} className="inline-link">
                    Bulk Calling
                </Link>{' '}
                page and upload a CSV file of the people to call, then come back here.
            </p>
            <div className="box-actions">
                <button type="button" className="primary" onClick={close}>
                    Return
                </button>
            </div>
        </>
    )
}

function BulkReady({ uid, files, voice, phoneCalls, onStarted }) {
    const close = useModalClose()
    const [proceeded, setProceeded] = useState(false)
    const [startBulk, { isLoading }] = useStartBulkCallMutation()
    const [error, setError] = useState(null)
    const people = files.reduce((n, f) => n + f.result.valid, 0)
    const proceed = async () => {
        if (!phoneCalls) return setProceeded(true) // not switched on: say so, place nothing
        setError(null)
        const file = csvFileFor(files[0].uploadedAt)
        if (!file) return setError('Please upload the CSV file again on the Bulk Calling page.')
        try {
            await startBulk({ uid, file }).unwrap()
            onStarted()
        } catch (err) {
            setError(errorMessage(err, 'Could not start the bulk call. Please try again.'))
        }
    }
    return (
        <>
            <p>
                {files.length === 1 ? 'A CSV file is' : `${files.length} CSV files are`} ready for a bulk
                call.
            </p>
            <ul className="bulk-queue" aria-label="CSV files in the queue">
                {files.map((f) => (
                    <li key={f.fileName + f.uploadedAt}>
                        <span className="mono">{f.fileName}</span>
                        <span className="muted">
                            {f.result.valid} {f.result.valid === 1 ? 'person' : 'people'} ready
                            {f.result.invalid > 0 ? ` · ${f.result.invalid} with errors (skipped)` : ''}
                        </span>
                    </li>
                ))}
            </ul>
            <VoiceNote voice={voice} />
            {phoneCalls && (
                <p className="muted">
                    The agent will phone each person in turn, one call at a time. You can pause or cancel at
                    any time.
                </p>
            )}
            {error && (
                <div className="banner error" role="alert">
                    {error}
                </div>
            )}
            {proceeded ? (
                <div className="banner notice" role="status">
                    Bulk calling is not switched on yet, so no calls were placed to these {people}{' '}
                    {people === 1 ? 'person' : 'people'}.
                </div>
            ) : null}
            <div className="box-actions">
                <button type="button" onClick={close}>
                    {proceeded ? 'Close' : 'Cancel'}
                </button>
                {!proceeded && (
                    <button
                        type="button"
                        className="primary"
                        onClick={() => void proceed()}
                        disabled={isLoading}
                    >
                        {isLoading ? 'Starting…' : 'Proceed with the bulk call'}
                    </button>
                )}
            </div>
        </>
    )
}

/**
 * "Call Agent" next to the agent tile: a two-item menu (Individual Call / Bulk Call), each opening its pop-up. While
 * a call is live in this tab it becomes a way back to that call instead, so a second call cannot be started.
 */
export default function CallAgent({ uid, voice }) {
    const status = useAppSelector((s) => s.call.status)
    const [menu, setMenu] = useState(false)
    const [dialog, setDialog] = useState(null) // 'individual' | 'bulk' | null
    const wrapRef = useRef(null)
    const buttonRef = useRef(null)
    const menuId = useId()

    useEffect(() => {
        if (!menu) return undefined
        wrapRef.current?.querySelector('[role="menuitem"]')?.focus()
        const onKey = (e) => {
            const items = [...(wrapRef.current?.querySelectorAll('[role="menuitem"]') ?? [])]
            const i = items.indexOf(document.activeElement)
            if (e.key === 'Escape') {
                setMenu(false)
                buttonRef.current?.focus()
            } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault()
                const step = e.key === 'ArrowDown' ? 1 : -1
                items[(i + step + items.length) % items.length]?.focus()
            } else if (e.key === 'Tab') setMenu(false)
        }
        const onDown = (e) => !wrapRef.current?.contains(e.target) && setMenu(false)
        document.addEventListener('keydown', onKey)
        document.addEventListener('mousedown', onDown)
        return () => {
            document.removeEventListener('keydown', onKey)
            document.removeEventListener('mousedown', onDown)
        }
    }, [menu])

    if (LIVE.includes(status))
        return (
            <Link className="button primary call-agent-button" to={`/call/${uid}`}>
                Return to call
            </Link>
        )
    const pick = (d) => {
        setMenu(false)
        setDialog(d)
    }
    return (
        <div className="call-agent" ref={wrapRef}>
            <button
                ref={buttonRef}
                type="button"
                className="primary call-agent-button"
                aria-haspopup="menu"
                aria-expanded={menu}
                aria-controls={menu ? menuId : undefined}
                onClick={() => setMenu((m) => !m)}
            >
                Call Agent
                <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden className={menu ? 'flip' : ''}>
                    <path
                        d="m6 9 6 6 6-6"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                    />
                </svg>
            </button>
            {menu && (
                <div className="call-menu" role="menu" id={menuId} aria-label="Type of call">
                    <button type="button" role="menuitem" onClick={() => pick('individual')}>
                        <strong>Individual Call</strong>
                        <span className="muted">Talk to your agent as one client</span>
                    </button>
                    <button type="button" role="menuitem" onClick={() => pick('bulk')}>
                        <strong>Bulk Call</strong>
                        <span className="muted">Call everyone in your uploaded CSV</span>
                    </button>
                </div>
            )}
            {dialog === 'individual' && (
                <IndividualCallModal uid={uid} voice={voice} onClose={() => setDialog(null)} />
            )}
            {dialog === 'bulk' && <BulkCallModal uid={uid} voice={voice} onClose={() => setDialog(null)} />}
        </div>
    )
}
