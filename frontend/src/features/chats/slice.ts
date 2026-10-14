import { createListenerMiddleware } from '@reduxjs/toolkit'
import { api } from '../../api/api'
import { callEnded } from '../call/slice'

/** After a call ends, poll the call until its summary is READY/FAILED, then refresh the sidebar list
 * so the chat title updates in place. */
export const summaryListener = createListenerMiddleware()

export const POLL_MS = 1500
export const POLL_MAX_MS = 120_000

summaryListener.startListening({
  actionCreator: callEnded,
  effect: async (_action, { dispatch, getState, cancelActiveListeners, delay }) => {
    cancelActiveListeners()
    const id = (getState() as { call: { currentCallId: string | null } }).call.currentCallId
    if (!id) return
    const deadline = Date.now() + POLL_MAX_MS
    while (Date.now() < deadline) {
      const res = await dispatch(api.endpoints.getCall.initiate(id, { forceRefetch: true }))
      const status = res.data?.summary_status
      if (status === 'READY' || status === 'FAILED') break
      await delay(POLL_MS)
    }
    dispatch(api.util.invalidateTags(['Calls']))
  },
})
