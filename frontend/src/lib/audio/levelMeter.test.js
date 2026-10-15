import { rmsFromTimeDomain } from './levelMeter'
it('silence (128) is zero, full-scale square wave is ~1', () => {
  expect(rmsFromTimeDomain(new Uint8Array(64).fill(128))).toBe(0)
  const sq = new Uint8Array(64).map((_, i) => (i % 2 ? 255 : 1))
  expect(rmsFromTimeDomain(sq)).toBeGreaterThan(0.98)
})
