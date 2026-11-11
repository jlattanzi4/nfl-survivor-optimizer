import assert from 'node:assert/strict';
import { test } from 'node:test';

import { STALE_AFTER_HOURS, staleNotice } from '../../docs/js/freshness.js';

const BUILT = '2026-11-11T19:20:57+00:00';
const hoursLater = (h) => Date.parse(BUILT) + h * 3600_000;

test('data refreshed on schedule gets no notice', () => {
  assert.equal(staleNotice(BUILT, hoursLater(0)), null);
  assert.equal(staleNotice(BUILT, hoursLater(8)), null);
});

test('a refresh that ran hours late still gets no notice', () => {
  // The longest gap between two scheduled runs so far is 13.9 hours; that is not news.
  assert.equal(staleNotice(BUILT, hoursLater(14)), null);
  assert.equal(staleNotice(BUILT, hoursLater(STALE_AFTER_HOURS)), null);
});

test('data older than the limit says how old it is', () => {
  assert.match(staleNotice(BUILT, hoursLater(STALE_AFTER_HOURS + 1)), /19 hours ago/);
  assert.match(staleNotice(BUILT, hoursLater(26)), /26 hours ago/);
});

test('after two days the age is given in days', () => {
  assert.match(staleNotice(BUILT, hoursLater(60)), /3 days ago/);
});

test('a missing or unreadable timestamp counts as stale', () => {
  assert.match(staleNotice(undefined, hoursLater(0)), /unknown/);
  assert.match(staleNotice('not a time', hoursLater(0)), /unknown/);
});

test('a clock that is behind the build does not trip the notice', () => {
  assert.equal(staleNotice(BUILT, hoursLater(-2)), null);
});
