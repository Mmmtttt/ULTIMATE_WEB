import assert from 'node:assert/strict'
import test from 'node:test'
import {
  calculateLoadSequence,
  clampPage,
  READER_LOAD_WINDOW,
  estimateReaderPageExtent,
  estimateReaderRangeExtent
} from '../../../../comic_frontend/src/composables/readerLoadWindow.js'

test('reader load sequence stays inside the requested window', () => {
  const pages = calculateLoadSequence(50, 1000, { minPage: 30, maxPage: 80 })

  assert.equal(pages.length, 51)
  assert.equal(pages[0], 50)
  assert.equal(new Set(pages).size, pages.length)
  assert.ok(pages.every((page) => page >= 30 && page <= 80))
})

test('reader load window clamps at comic boundaries', () => {
  assert.deepEqual(
    calculateLoadSequence(2, 5, { minPage: 1, maxPage: 5 }),
    [2, 3, 4, 5, 1]
  )
  assert.equal(clampPage(999, 5), 5)
  assert.equal(clampPage(-1, 5), 1)
  assert.equal(READER_LOAD_WINDOW.normalBefore, 20)
  assert.equal(READER_LOAD_WINDOW.normalAfter, 60)
})

test('reader placeholder estimates preserve known image ratios and sparse ranges', () => {
  assert.equal(
    estimateReaderPageExtent({ width: 1000, height: 1500 }, {
      pageMode: 'up_down',
      viewportWidth: 1000,
      viewportHeight: 800
    }),
    800
  )
  assert.equal(
    estimateReaderPageExtent({ width: 1000, height: 500 }, {
      pageMode: 'left_right',
      viewportWidth: 1000,
      viewportHeight: 800,
      doublePageMode: true
    }),
    500
  )
  assert.equal(
    estimateReaderRangeExtent({ 2: { width: 1000, height: 1000 } }, 1, 3, {
      pageMode: 'up_down',
      viewportWidth: 1000,
      viewportHeight: 800
    }),
    2112
  )
})
