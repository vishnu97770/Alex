export function rmsFromTimeDomain(data) {
  let sum = 0
  for (let i = 0; i < data.length; i++) {
    const v = (data[i] - 128) / 128
    sum += v * v
  }
  return Math.sqrt(sum / data.length)
}
export function createLevelMeter(track) {
  const Ctx = window.AudioContext ?? window.webkitAudioContext
  const ctx = new Ctx()
  const source = ctx.createMediaStreamSource(new MediaStream([track]))
  const analyser = ctx.createAnalyser()
  analyser.fftSize = 512
  analyser.smoothingTimeConstant = 0.6
  source.connect(analyser) // intentionally not connected to destination: no echo, no double playback
  const buf = new Uint8Array(analyser.fftSize)
  let smoothed = 0
  return {
    getLevel() {
      analyser.getByteTimeDomainData(buf)
      const raw = Math.min(1, rmsFromTimeDomain(buf) * 4)
      smoothed = raw > smoothed ? raw : smoothed * 0.85 + raw * 0.15
      return smoothed
    },
    close() {
      try {
        source.disconnect()
      } catch {
        /* already disconnected */
      }
      void ctx.close().catch(() => undefined)
    },
  }
}
