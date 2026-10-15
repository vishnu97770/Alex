import { createSlice } from '@reduxjs/toolkit'
import { api } from '../../api/api'
const initialState = { activeProfileId: null, generation: 'idle', error: null }
const errMsg = (p) => {
  const e = p
  return e?.data?.error?.message ?? 'Something went wrong. Please try again.'
}
export const agentProfileSlice = createSlice({
  name: 'agentProfile',
  initialState,
  reducers: {},
  extraReducers: (b) => {
    b.addMatcher(api.endpoints.generateProfile.matchPending, (s) => {
      s.generation = 'pending'
      s.error = null
    })
    b.addMatcher(api.endpoints.generateProfile.matchFulfilled, (s, { payload }) => {
      s.generation = 'idle'
      s.activeProfileId = payload.profile_id
    })
    b.addMatcher(api.endpoints.generateProfile.matchRejected, (s, { payload, meta }) => {
      if (meta.aborted) {
        s.generation = 'idle' // user cancelled: not an error
        s.error = null
        return
      }
      s.generation = 'failed'
      s.error = errMsg(payload)
    })
    b.addMatcher(api.endpoints.getActiveProfile.matchFulfilled, (s, { payload }) => {
      s.activeProfileId = payload.profile_id
    })
  },
})
export default agentProfileSlice.reducer
