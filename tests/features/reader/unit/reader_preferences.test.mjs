import assert from 'node:assert/strict'
import test from 'node:test'
import { resolveTapPageAction } from '../../../../comic_frontend/src/composables/useReaderPreferences.js'

test('reader tap modes map to the expected page action', () => {
  assert.equal(resolveTapPageAction({ mode: 'full', x: 20, width: 100 }), 'menu')
  assert.equal(resolveTapPageAction({ mode: 'left', x: 20, width: 100 }), 'previous')
  assert.equal(resolveTapPageAction({ mode: 'left', x: 80, width: 100 }), 'none')
  assert.equal(resolveTapPageAction({ mode: 'right', x: 80, width: 100 }), 'next')
  assert.equal(resolveTapPageAction({ mode: 'right', x: 20, width: 100 }), 'none')
})

test('webtoon tap turning can be disabled without changing page-zone settings', () => {
  assert.equal(resolveTapPageAction({ mode: 'left', x: 20, width: 100, isWebtoon: true, webtoonEnabled: false }), 'menu')
})
