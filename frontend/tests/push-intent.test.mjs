import assert from 'node:assert/strict';
import test from 'node:test';

import {
	PUSH_INTENT_KEY,
	clearPushIntent,
	getPushIntent,
	setPushIntent
} from '../src/lib/push-intent.ts';

/** In-memory Storage stand-in so tests never touch a real browser API. */
function createMemoryStorage() {
	const store = new Map();
	return {
		getItem: (key) => (store.has(key) ? store.get(key) : null),
		setItem: (key, value) => store.set(key, String(value)),
		removeItem: (key) => store.delete(key)
	};
}

/** A Storage stand-in whose every method throws, like Safari private mode. */
function createThrowingStorage() {
	const boom = () => {
		throw new Error('storage disabled');
	};
	return { getItem: boom, setItem: boom, removeItem: boom };
}

test('PUSH_INTENT_KEY is the app-prefixed storage key', () => {
	assert.equal(PUSH_INTENT_KEY, 'jamye:push-intent');
});

test('setPushIntent/getPushIntent/clearPushIntent round-trip the user id', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		assert.equal(getPushIntent(), null, 'starts empty');

		setPushIntent('user-123');
		assert.equal(getPushIntent(), 'user-123', 'getPushIntent returns exactly the stored id');

		clearPushIntent();
		assert.equal(getPushIntent(), null, 'clearPushIntent removes the key');
	} finally {
		delete globalThis.localStorage;
	}
});

test('accessors are safe when localStorage is unavailable', () => {
	delete globalThis.localStorage;
	assert.equal(typeof localStorage, 'undefined', 'precondition: no localStorage global');

	assert.equal(getPushIntent(), null, 'getPushIntent returns null without localStorage');
	assert.doesNotThrow(() => setPushIntent('user-123'), 'setPushIntent is a no-op');
	assert.doesNotThrow(() => clearPushIntent(), 'clearPushIntent is a no-op');
});

test('accessors swallow a throwing localStorage instead of propagating', () => {
	globalThis.localStorage = createThrowingStorage();
	try {
		assert.doesNotThrow(() => getPushIntent(), 'getPushIntent swallows the thrown error');
		assert.equal(getPushIntent(), null, 'getPushIntent falls back to null on throw');
		assert.doesNotThrow(() => setPushIntent('user-123'), 'setPushIntent swallows the thrown error');
		assert.doesNotThrow(() => clearPushIntent(), 'clearPushIntent swallows the thrown error');
	} finally {
		delete globalThis.localStorage;
	}
});
