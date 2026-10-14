export interface Profile {
  profile_id: string
  version: number
  context_prompt: string
  structured_fields: Record<string, unknown>
  placeholders: string[]
  assumptions_made: string[]
}

export interface CallSummary {
  title: string
  summary: string
  call_outcome: string
  key_points: string[]
  user_requests: string[]
  agent_commitments_and_next_actions: { action: string; owner: string; due_if_stated: string | null }[]
  unresolved_items: string[]
  information_collected: Record<string, string>
  sentiment: string
  escalation_needed: boolean
  escalation_reason: string | null
  topics_outside_scope_raised: string[]
  confidence_notes: string
}

export type SummaryStatus = 'PENDING' | 'READY' | 'FAILED'

export interface CallListItem {
  id: string
  title: string | null
  status: string
  summary_status: SummaryStatus
  started_at: string | null
}

export interface CallDetail extends CallListItem {
  ended_at: string | null
  end_reason: string | null
  turns: { seq: number; speaker: 'user' | 'agent'; text: string; is_final: boolean }[]
  summary: CallSummary | null
}

export interface CreateCallResponse {
  call_id: string
  livekit_url: string
  token: string
}
