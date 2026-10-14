import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type { CallDetail, CallListItem, CreateCallResponse, Profile } from '../types/api'

export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: `${location.origin}/api/v1`, credentials: 'include' }),
  tagTypes: ['Profile', 'Calls'],
  endpoints: (b) => ({
    getActiveProfile: b.query<Profile, void>({
      query: () => '/agent-profiles/active',
      providesTags: ['Profile'],
    }),
    generateProfile: b.mutation<Profile, { description: string }>({
      query: (body) => ({ url: '/agent-profiles/generate', method: 'POST', body }),
      invalidatesTags: ['Profile'],
    }),
    updateProfile: b.mutation<Profile, { id: string; context_prompt: string }>({
      query: ({ id, context_prompt }) => ({
        url: `/agent-profiles/${id}`,
        method: 'PUT',
        body: { context_prompt },
      }),
      invalidatesTags: ['Profile'],
    }),
    createCall: b.mutation<CreateCallResponse, void>({
      query: () => ({ url: '/calls', method: 'POST', body: {} }),
      invalidatesTags: ['Calls'],
    }),
    endCall: b.mutation<{ status: string }, string>({
      query: (id) => ({ url: `/calls/${id}/end`, method: 'POST' }),
    }),
    listCalls: b.query<CallListItem[], void>({ query: () => '/calls', providesTags: ['Calls'] }),
    getCall: b.query<CallDetail, string>({ query: (id) => `/calls/${id}` }),
  }),
})

export const {
  useGetActiveProfileQuery,
  useGenerateProfileMutation,
  useUpdateProfileMutation,
  useCreateCallMutation,
  useEndCallMutation,
  useListCallsQuery,
  useGetCallQuery,
} = api
