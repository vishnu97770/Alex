/** Owns the LiveKit Room and audio analysers. Deliberately outside Redux (non-serializable). */
import { ConnectionState, DisconnectReason, ParticipantKind, Room, RoomEvent, Track } from 'livekit-client'
import { createLevelMeter } from '../audio/levelMeter'
// Verified in livekit-client / components-core: topic and attribute names.
export const TRANSCRIPTION_TOPIC = 'lk.transcription'
export const ATTR = {
  segmentId: 'lk.segment_id',
  trackId: 'lk.transcribed_track_id',
  final: 'lk.transcription_final',
  agentState: 'lk.agent.state',
}
// Agent startup (process spawn + LiveKit connect) can take 10-15s; be generous before declaring failure.
export const AGENT_JOIN_TIMEOUT_MS = 45_000
/** A server-side end (agent closed the room) is a normal hang-up, not a connection error. */
export function isNormalDisconnect(reason) {
  return reason === DisconnectReason.ROOM_DELETED || reason === DisconnectReason.CLIENT_INITIATED
}
export const AGENT_LEFT_GRACE_MS = 1500
export function classifySpeaker(trackId, localMicSid) {
  return trackId && localMicSid && trackId === localMicSid ? 'user' : 'agent'
}
export class CallRoomManager {
  room = null
  userMeter = null
  agentMeter = null
  joinTimer = null
  intentionalClose = false
  audioEls = new Set()
  getLevels() {
    return { user: this.userMeter?.getLevel() ?? 0, agent: this.agentMeter?.getLevel() ?? 0 }
  }
  async connect(url, token, cb) {
    this.intentionalClose = false
    const room = new Room({ adaptiveStream: true, dynacast: true })
    this.room = room
    room.on(RoomEvent.ConnectionStateChanged, (st) => {
      if (st === ConnectionState.Reconnecting) cb.onStatus('reconnecting')
      else if (st === ConnectionState.Connected)
        cb.onStatus(this.hasAgent() ? 'connected' : 'waiting_for_agent')
    })
    room.on(RoomEvent.ParticipantConnected, (p) => {
      if (p.kind === ParticipantKind.AGENT) this.agentJoined(cb)
    })
    room.on(RoomEvent.ParticipantAttributesChanged, (_changed, p) => {
      if (p.kind === ParticipantKind.AGENT && p.attributes[ATTR.agentState]) {
        cb.onAgentState(p.attributes[ATTR.agentState])
      }
    })
    room.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
      if (track.kind === Track.Kind.Audio && participant.kind === ParticipantKind.AGENT) {
        this.agentMeter?.close()
        this.agentMeter = createLevelMeter(track.mediaStreamTrack)
        // livekit-client does not play remote audio by itself: attach to a hidden <audio> element.
        const el = track.attach()
        el.style.display = 'none'
        document.body.appendChild(el)
        this.audioEls.add(el)
      }
    })
    room.on(RoomEvent.TrackUnsubscribed, (track) => {
      track.detach().forEach((el) => {
        el.remove()
        this.audioEls.delete(el)
      })
    })
    room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
      if (!room.canPlaybackAudio)
        cb.onError('Your browser blocked audio. Click anywhere on the page to enable sound.')
    })
    room.on(RoomEvent.MediaDevicesError, () =>
      cb.onError('Microphone problem. Check permissions and devices.'),
    )
    room.on(RoomEvent.ParticipantDisconnected, (p) => {
      // The agent hung up. The server normally closes the room too; this is the fallback so the
      // browser never stays "connected" to an empty call.
      if (p.kind !== ParticipantKind.AGENT) return
      setTimeout(() => {
        if (this.room === room && !this.hasAgent()) void this.disconnect().then(cb.onDisconnected)
      }, AGENT_LEFT_GRACE_MS)
    })
    room.on(RoomEvent.Disconnected, (reason) => {
      this.cleanup()
      if (!this.intentionalClose && !isNormalDisconnect(reason)) cb.onError('The connection was lost.')
      cb.onDisconnected()
    })
    room.registerTextStreamHandler(TRANSCRIPTION_TOPIC, async (reader) => {
      const attrs = reader.info.attributes ?? {}
      const id = attrs[ATTR.segmentId] ?? reader.info.id
      const speaker = classifySpeaker(attrs[ATTR.trackId], this.localMicSid())
      const flagged = attrs[ATTR.final] === 'true'
      let acc = ''
      for await (const delta of reader) {
        acc += delta // reader yields deltas; accumulate within one stream
        cb.onSegment({ id, speaker, text: acc, isFinal: false })
      }
      // Stream end: agent segments are complete; user interim updates only finalize via the attribute.
      cb.onSegment({ id, speaker, text: acc, isFinal: flagged || speaker === 'agent' })
    })
    cb.onStatus('connecting')
    await room.connect(url, token)
    await room.startAudio().catch(() => undefined) // within the user's click gesture: unlock playback
    try {
      await room.localParticipant.setMicrophoneEnabled(true)
    } catch {
      cb.onError('Microphone access was denied. Allow the microphone and try again.')
      await this.disconnect()
      return
    }
    const mic = room.localParticipant.getTrackPublication(Track.Source.Microphone)?.track
    if (mic) this.userMeter = createLevelMeter(mic.mediaStreamTrack)
    if (this.hasAgent()) this.agentJoined(cb)
    else {
      cb.onStatus('waiting_for_agent')
      this.joinTimer = setTimeout(() => {
        if (!this.hasAgent()) {
          cb.onError('The agent did not join the call. Please try again.')
          void this.disconnect()
        }
      }, AGENT_JOIN_TIMEOUT_MS)
    }
  }
  agentJoined(cb) {
    if (this.joinTimer) clearTimeout(this.joinTimer)
    this.joinTimer = null
    cb.onStatus('connected')
  }
  hasAgent() {
    return (
      !!this.room && [...this.room.remoteParticipants.values()].some((p) => p.kind === ParticipantKind.AGENT)
    )
  }
  localMicSid() {
    return this.room?.localParticipant.getTrackPublication(Track.Source.Microphone)?.trackSid
  }
  async setMuted(muted) {
    await this.room?.localParticipant.setMicrophoneEnabled(!muted)
  }
  async disconnect() {
    this.intentionalClose = true
    const room = this.room
    this.cleanup()
    await room?.disconnect()
  }
  cleanup() {
    if (this.joinTimer) clearTimeout(this.joinTimer)
    this.joinTimer = null
    this.userMeter?.close()
    this.agentMeter?.close()
    this.userMeter = this.agentMeter = null
    this.audioEls.forEach((el) => el.remove())
    this.audioEls.clear()
    this.room = null
  }
}
