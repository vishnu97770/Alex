import { createSlice } from '@reduxjs/toolkit'
export const initialState = {
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
    callStarting: (_s, a) => ({
      ...initialState,
      status: 'connecting',
      currentCallId: a.payload,
    }),
    statusChanged: (s, a) => {
      s.status = a.payload
    },
    agentStateChanged: (s, a) => {
      s.agentState = a.payload
    },
    muteChanged: (s, a) => {
      s.muted = a.payload
    },
    callFailed: (s, a) => {
      s.status = 'failed'
      s.error = a.payload
      s.agentState = 'idle'
    },
    callEnded: (s, _a) => {
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
