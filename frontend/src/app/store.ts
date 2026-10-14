import { configureStore } from '@reduxjs/toolkit'
import { api } from '../api/api'
import agentProfile from '../features/agentProfile/slice'
import call from '../features/call/slice'
import { summaryListener } from '../features/chats/slice'
import transcript from '../features/transcript/slice'

export const makeStore = () =>
  configureStore({
    reducer: { [api.reducerPath]: api.reducer, agentProfile, call, transcript },
    middleware: (gdm) => gdm().prepend(summaryListener.middleware).concat(api.middleware),
  })

export const store = makeStore()
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
