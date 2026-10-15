import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
export const api = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({ baseUrl: `${location.origin}/api/v1`, credentials: 'include' }),
  tagTypes: ['Profile', 'Calls'],
  endpoints: (b) => ({
    getActiveProfile: b.query({
      query: () => '/agent-profiles/active',
      providesTags: ['Profile'],
    }),
    generateProfile: b.mutation({
      query: (body) => ({ url: '/agent-profiles/generate', method: 'POST', body }),
      invalidatesTags: ['Profile'],
    }),
    updateProfile: b.mutation({
      query: ({ id, context_prompt }) => ({
        url: `/agent-profiles/${id}`,
        method: 'PUT',
        body: { context_prompt },
      }),
      invalidatesTags: ['Profile'],
    }),
    createCall: b.mutation({
      query: () => ({ url: '/calls', method: 'POST', body: {} }),
      invalidatesTags: ['Calls'],
    }),
    endCall: b.mutation({
      query: (id) => ({ url: `/calls/${id}/end`, method: 'POST' }),
    }),
    listCalls: b.query({ query: () => '/calls', providesTags: ['Calls'] }),
    getCall: b.query({ query: (id) => `/calls/${id}` }),
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
