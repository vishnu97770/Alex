import { createSelector, createSlice } from '@reduxjs/toolkit'
export const initialState = { byId: {}, ids: [], nextOrder: 0 }
export const transcriptSlice = createSlice({
  name: 'transcript',
  initialState,
  reducers: {
    /** Interim -> final replacement in place. Later updates replace text; a final entry is never un-finalized
     * and a stale interim arriving after the final is ignored (out-of-order / duplicate safe). */
    segmentUpserted: (s, a) => {
      const { id, speaker, text, isFinal } = a.payload
      const cur = s.byId[id]
      if (!cur) {
        s.byId[id] = { id, speaker, text, isFinal, order: s.nextOrder++ }
        s.ids.push(id)
        return
      }
      if (cur.isFinal && !isFinal) return
      cur.text = text
      cur.isFinal = cur.isFinal || isFinal
    },
    transcriptCleared: () => initialState,
  },
})
export const { segmentUpserted, transcriptCleared } = transcriptSlice.actions
export default transcriptSlice.reducer
const selectTranscript = (st) => st.transcript
/** Memoized: only returns a new array when the transcript state actually changes. */
export const selectEntries = createSelector([selectTranscript], (t) => t.ids.map((id) => t.byId[id]))
