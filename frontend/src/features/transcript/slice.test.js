import reducer, { segmentUpserted, selectEntries, transcriptCleared } from './slice'
const up = (id, text, isFinal = false, speaker = 'user') => segmentUpserted({ id, speaker, text, isFinal })
const run = (...actions) => actions.reduce(reducer, undefined)
const entries = (s) => selectEntries({ transcript: s })
describe('transcript merge', () => {
  it('replaces interim text in place and finalizes', () => {
    const s = run(up('a', 'hel'), up('a', 'hello'), up('a', 'hello there', true))
    expect(entries(s)).toEqual([{ id: 'a', speaker: 'user', text: 'hello there', isFinal: true, order: 0 }])
  })
  it('keeps arrival order across segments', () => {
    const s = run(up('u1', 'hi', true), up('a1', 'hello', true, 'agent'), up('u2', 'bye'))
    expect(entries(s).map((e) => e.id)).toEqual(['u1', 'a1', 'u2'])
  })
  it('ignores a stale interim arriving after the final', () => {
    const s = run(up('a', 'done', true), up('a', 'do'))
    expect(entries(s)[0]).toMatchObject({ text: 'done', isFinal: true })
  })
  it('is idempotent for duplicate final segments', () => {
    const s = run(up('a', 'x', true), up('a', 'x', true))
    expect(entries(s)).toHaveLength(1)
  })
  it('does not reorder when an old segment updates late', () => {
    const s = run(up('a', 'one'), up('b', 'two'), up('a', 'one!', true))
    expect(entries(s).map((e) => e.id)).toEqual(['a', 'b'])
  })
  it('clears', () => {
    expect(reducer(run(up('a', 'x')), transcriptCleared()).ids).toEqual([])
  })
})
