import { ATTR, TRANSCRIPTION_TOPIC, classifySpeaker } from './roomManager'
it('uses the verified LiveKit topic and attribute names', () => {
  expect(TRANSCRIPTION_TOPIC).toBe('lk.transcription')
  expect(ATTR).toMatchObject({
    segmentId: 'lk.segment_id',
    trackId: 'lk.transcribed_track_id',
    final: 'lk.transcription_final',
    agentState: 'lk.agent.state',
  })
})
it('classifies user speech by the local mic track id, everything else as agent', () => {
  expect(classifySpeaker('TR_mic', 'TR_mic')).toBe('user')
  expect(classifySpeaker('TR_agent', 'TR_mic')).toBe('agent')
  expect(classifySpeaker(undefined, 'TR_mic')).toBe('agent')
})
import { DisconnectReason } from 'livekit-client'
import { isNormalDisconnect } from './roomManager'
it('treats a server-closed room and a client hang-up as normal ends, but not a dropped connection', () => {
  expect(isNormalDisconnect(DisconnectReason.ROOM_DELETED)).toBe(true)
  expect(isNormalDisconnect(DisconnectReason.CLIENT_INITIATED)).toBe(true)
  expect(isNormalDisconnect(DisconnectReason.JOIN_FAILURE)).toBe(false)
  expect(isNormalDisconnect(undefined)).toBe(false)
})
