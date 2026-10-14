/** Owns the LiveKit Room and audio analysers. Deliberately outside Redux (non-serializable). */
import {
  ConnectionState,
  ParticipantKind,
  Room,
  RoomEvent,
  Track,
  type Participant,
  type RemoteTrack,
} from 'livekit-client'
import { createLevelMeter, type LevelMeter } from '../audio/levelMeter'
import type { AgentState, ConnectionStatus } from '../../features/call/slice'
import type { Upsert } from '../../features/transcript/slice'

// Verified in livekit-client / components-core: topic and attribute names.
export const TRANSCRIPTION_TOPIC = 'lk.transcription'
export const ATTR = {
  segmentId: 'lk.segment_id',
  trackId: 'lk.transcribed_track_id',
  final: 'lk.transcription_final',
  agentState: 'lk.agent.state',
} as const

// Agent startup (process spawn + LiveKit connect) can take 10-15s; be generous before declaring failure.
export const AGENT_JOIN_TIMEOUT_MS = 45_000

export interface Callbacks {
  onStatus(s: ConnectionStatus): void
  onAgentState(s: AgentState): void
  onSegment(u: Upsert): void
  onError(message: string): void
  onDisconnected(): void
}

export function classifySpeaker(
  trackId: string | undefined,
  localMicSid: string | undefined,
): 'user' | 'agent' {
  return trackId && localMicSid && trackId === localMicSid ? 'user' : 'agent'
}

export class CallRoomManager {
  private room: Room | null = null
  private userMeter: LevelMeter | null = null
  private agentMeter: LevelMeter | null = null
  private joinTimer: ReturnType<typeof setTimeout> | null = null
  private intentionalClose = false
  private audioEls = new Set<HTMLMediaElement>()

  getLevels() {
    return { user: this.userMeter?.getLevel() ?? 0, agent: this.agentMeter?.getLevel() ?? 0 }
  }

  async connect(url: string, token: string, cb: Callbacks): Promise<void> {
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
    room.on(RoomEvent.ParticipantAttributesChanged, (_changed, p: Participant) => {
      if (p.kind === ParticipantKind.AGENT && p.attributes[ATTR.agentState]) {
        cb.onAgentState(p.attributes[ATTR.agentState] as AgentState)
      }
    })
    room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, _pub, participant) => {
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
    room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
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
    room.on(RoomEvent.Disconnected, () => {
      this.cleanup()
      if (!this.intentionalClose) cb.onError('The connection was lost.')
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

  private agentJoined(cb: Callbacks) {
    if (this.joinTimer) clearTimeout(this.joinTimer)
    this.joinTimer = null
    cb.onStatus('connected')
  }

  private hasAgent(): boolean {
    return (
      !!this.room && [...this.room.remoteParticipants.values()].some((p) => p.kind === ParticipantKind.AGENT)
    )
  }

  private localMicSid(): string | undefined {
    return this.room?.localParticipant.getTrackPublication(Track.Source.Microphone)?.trackSid
  }

  async setMuted(muted: boolean) {
    await this.room?.localParticipant.setMicrophoneEnabled(!muted)
  }

  async disconnect() {
    this.intentionalClose = true
    const room = this.room
    this.cleanup()
    await room?.disconnect()
  }

  private cleanup() {
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
