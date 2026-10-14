import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useGetActiveProfileQuery, useUpdateProfileMutation } from '../api/api'

export default function SettingsPage() {
  const { data } = useGetActiveProfileQuery()
  const [save, { isLoading, isSuccess, isError }] = useUpdateProfileMutation()
  const [draft, setDraft] = useState<string | null>(null)
  const text = draft ?? data?.context_prompt ?? ''
  const setText = setDraft

  if (!data)
    return (
      <div className="role">
        <p className="muted">No agent role yet.</p>
        <Link to="/">Set one up</Link>
      </div>
    )
  const remaining = data.placeholders.filter((p) => text.includes(p))
  return (
    <div className="settings">
      <h1>Agent role</h1>
      <p className="muted">
        Version {data.version}. Saving creates a new version; past calls are unaffected.
      </p>
      {remaining.length > 0 && (
        <div className="banner warn">Replace these markers with your facts: {remaining.join(', ')}</div>
      )}
      <textarea
        aria-label="Context prompt"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={22}
      />
      <div className="row">
        <button
          className="primary"
          disabled={isLoading || text === data.context_prompt}
          onClick={() => void save({ id: data.profile_id, context_prompt: text })}
        >
          {isLoading ? 'Saving…' : 'Save new version'}
        </button>
        <Link to="/">Start over</Link>
        {isSuccess && <span className="muted">Saved.</span>}
        {isError && <span role="alert">Could not save.</span>}
      </div>
    </div>
  )
}
