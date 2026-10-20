import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

export const readCookie = (name) => {
  try {
    const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
    return m ? decodeURIComponent(m[1]) : null
  } catch {
    return null
  }
}

const raw = fetchBaseQuery({
  baseUrl: `${location.origin}/api/v1`,
  credentials: 'include',
  prepareHeaders: (headers) => {
    const csrf = readCookie('csrf_token')
    if (csrf) headers.set('X-CSRF-Token', csrf)
    return headers
  },
})

// Endpoints whose 401 is an expected answer rather than an expired session.
const AUTH_QUIET = new Set(['me', 'login', 'register'])

const baseQuery = async (args, api, extra) => {
  const result = await raw(args, api, extra)
  if (result.error?.status === 401 && !AUTH_QUIET.has(api.endpoint)) {
    if (location.pathname !== '/checkin') location.assign('/checkin')
  }
  return result
}

const browserTimeZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined
  } catch {
    return undefined
  }
}

const serverDown = (err) =>
  err?.status === 'FETCH_ERROR' || err?.status === 'PARSING_ERROR' || err?.status >= 500

export const errorMessage = (err, fallback = 'Something went wrong. Please try again.') =>
  err?.data?.error?.message ??
  (Array.isArray(err?.data?.detail) ? err.data.detail[0]?.msg : undefined) ??
  (serverDown(err) ? 'Cannot reach the server. Please make sure the backend is running.' : fallback)

export const api = createApi({
  reducerPath: 'api',
  baseQuery,
  tagTypes: ['Profile', 'Calls', 'Me', 'Agents', 'Usage', 'ScreenTime'],
  endpoints: (b) => ({
    // --- auth / user ---
    authConfig: b.query({ query: () => '/auth/config' }),
    me: b.query({ query: () => '/auth/me', providesTags: ['Me'] }),
    register: b.mutation({
      query: (body) => ({ url: '/auth/register', method: 'POST', body }),
      invalidatesTags: ['Me'],
    }),
    login: b.mutation({
      query: (body) => ({ url: '/auth/login', method: 'POST', body }),
      invalidatesTags: ['Me'],
    }),
    logout: b.mutation({ query: () => ({ url: '/auth/logout', method: 'POST' }) }),
    uploadAvatar: b.mutation({
      query: ({ uid, file }) => ({
        url: `/users/${uid}/avatar`,
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
      }),
      invalidatesTags: ['Me'],
    }),
    // --- agents ---
    listAgents: b.query({ query: (uid) => `/users/${uid}/agents`, providesTags: ['Agents'] }),
    getAgent: b.query({ query: ({ uid, aid }) => `/users/${uid}/agents/${aid}`, providesTags: ['Agents'] }),
    createAgent: b.mutation({
      query: ({ uid, ...body }) => ({ url: `/users/${uid}/agents`, method: 'POST', body }),
    }),
    payAgent: b.mutation({
      query: ({ uid, aid, amount }) => ({
        url: `/users/${uid}/agents/${aid}/payment`,
        method: 'POST',
        body: { amount },
      }),
      invalidatesTags: ['Agents', 'Me'],
    }),
    updateAgent: b.mutation({
      query: ({ uid, aid, ...body }) => ({ url: `/users/${uid}/agents/${aid}`, method: 'PUT', body }),
      invalidatesTags: ['Agents'],
    }),
    // --- manager ---
    listManagerCalls: b.query({ query: (uid) => `/users/${uid}/manager/calls`, providesTags: ['Calls'] }),
    createManagerCall: b.mutation({
      query: (uid) => ({ url: `/users/${uid}/manager/calls`, method: 'POST' }),
      invalidatesTags: ['Calls'],
    }),
    // --- stats / screen time ---
    getUsage: b.query({
      query: ({ uid, metric, range, agentId }) => ({
        url: `/users/${uid}/stats/usage`,
        params: { metric, range, tz: browserTimeZone(), ...(agentId ? { agent_id: agentId } : {}) },
      }),
      providesTags: ['Usage'],
    }),
    getScreenTime: b.query({
      query: ({ uid, weekStart }) => ({
        url: `/users/${uid}/screen-time`,
        params: { tz: browserTimeZone(), ...(weekStart ? { week_start: weekStart } : {}) },
      }),
      providesTags: ['ScreenTime'],
    }),
    sendHeartbeat: b.mutation({
      query: ({ uid, seconds }) => ({
        url: `/users/${uid}/screen-time/heartbeat`,
        method: 'POST',
        body: { seconds, tz: browserTimeZone() },
      }),
    }),
    // --- existing voice-agent endpoints ---
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
  useAuthConfigQuery,
  useMeQuery,
  useRegisterMutation,
  useLoginMutation,
  useLogoutMutation,
  useUploadAvatarMutation,
  useListAgentsQuery,
  useGetAgentQuery,
  useCreateAgentMutation,
  usePayAgentMutation,
  useUpdateAgentMutation,
  useGetUsageQuery,
  useGetScreenTimeQuery,
  useListManagerCallsQuery,
  useCreateManagerCallMutation,
  useGetActiveProfileQuery,
  useGenerateProfileMutation,
  useUpdateProfileMutation,
  useCreateCallMutation,
  useEndCallMutation,
  useListCallsQuery,
  useGetCallQuery,
} = api
