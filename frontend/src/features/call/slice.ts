import { createSlice, type PayloadAction } from '@reduxjs/toolkit'

export type ConnectionStatus =
  'idle' | 'connecting' | 'waiting_for_agent' | 'connected' | 'reconnecting' | 'ended' | 'failed'
export type AgentState = 'idle' | 'initializing' | 'listening' | 'thinking' | 'speaking'

export interface CallState {
  status: ConnectionStatus
  agentState: AgentState
  muted: boolean
  currentCallId: string | null
  error: string | null
}
export const initialState: CallState = {
  status: 'idle',
  agentState: 'idle',
  muted: false,
  currentCallId: null,
  error: null,
}

export const callSlice = createSlice({
  name: 'call',
  initialState,
  reducers: {
    callStarting: (_s, a: PayloadAction<string>) => ({
      ...initialState,
      status: 'connecting',
      currentCallId: a.payload,
    }),
    statusChanged: (s, a: PayloadAction<ConnectionStatus>) => {
      s.status = a.payload
    },
    agentStateChanged: (s, a: PayloadAction<AgentState>) => {
      s.agentState = a.payload
    },
    muteChanged: (s, a: PayloadAction<boolean>) => {
      s.muted = a.payload
    },
    callFailed: (s, a: PayloadAction<string>) => {
      s.status = 'failed'
      s.error = a.payload
      s.agentState = 'idle'
    },
    callEnded: (s, _a: PayloadAction<string | undefined>) => {
      s.status = 'ended'
      s.agentState = 'idle'
    },
    callReset: () => initialState,
  },
})
export const {
  callStarting,
  statusChanged,
  agentStateChanged,
  muteChanged,
  callFailed,
  callEnded,
  callReset,
} = callSlice.actions
export default callSlice.reducer
