import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useAppDispatch } from '../../app/hooks'
import { useCreateCallMutation, useEndCallMutation } from '../../api/api'
import { CallRoomManager } from '../../lib/livekit/roomManager'
import { segmentUpserted, transcriptCleared } from '../transcript/slice'
import { agentStateChanged, callEnded, callFailed, callStarting, muteChanged, statusChanged } from './slice'
const Ctx = createContext(null)
export function CallProvider({ children }) {
    const dispatch = useAppDispatch()
    const [createCall] = useCreateCallMutation()
    const [endCallApi] = useEndCallMutation()
    const [manager] = useState(() => new CallRoomManager())
    const callId = useRef(null)
    const ended = useRef(false)
    const finish = useCallback(() => {
        if (ended.current) return
        ended.current = true
        dispatch(callEnded(callId.current ?? undefined))
    }, [dispatch])
    const start = useCallback(async () => {
        ended.current = false
        dispatch(transcriptCleared())
        try {
            const r = await createCall().unwrap()
            callId.current = r.call_id
            dispatch(callStarting(r.call_id))
            await manager.connect(r.livekit_url, r.token, {
                onStatus: (s) => dispatch(statusChanged(s)),
                onAgentState: (s) => dispatch(agentStateChanged(s)),
                onSegment: (u) => dispatch(segmentUpserted(u)),
                onError: (m) => dispatch(callFailed(m)),
                onDisconnected: finish,
            })
            return r.call_id
        } catch {
            dispatch(callFailed('Could not start the call. Please try again.'))
            return null
        }
    }, [createCall, dispatch, finish, manager])
    const end = useCallback(async () => {
        const id = callId.current
        await manager.disconnect()
        finish()
        if (id) void endCallApi(id)
    }, [endCallApi, finish, manager])
    const setMuted = useCallback(
        async (m) => {
            await manager.setMuted(m)
            dispatch(muteChanged(m))
        },
        [dispatch, manager],
    )
    useEffect(() => () => void manager.disconnect(), [manager])
    const value = useMemo(() => ({ manager, start, end, setMuted }), [manager, start, end, setMuted])
    return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
export function useCall() {
    const c = useContext(Ctx)
    if (!c) throw new Error('useCall outside CallProvider')
    return c
}
