import { progressMessage } from './useElapsed'
it('escalates the message as time passes, ending with an honest "busy" notice', () => {
  expect(progressMessage(0)).toMatch(/Reading/)
  expect(progressMessage(5)).toMatch(/Designing/)
  expect(progressMessage(30)).toMatch(/busy/i)
})
