import assert from 'node:assert/strict';
import test from 'node:test';

import {
	PUSH_INTENT_KEY,
	clearPushIntent,
	getPushIntent,
	hasExplicitPushOptOut,
	setPushIntent,
	setPushIntentOff
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
	assert.doesNotThrow(() => setPushIntentOff('user-123'), 'setPushIntentOff is a no-op');
	assert.equal(
		hasExplicitPushOptOut('user-123'),
		false,
		'hasExplicitPushOptOut is false without localStorage'
	);
});

test('accessors swallow a throwing localStorage instead of propagating', () => {
	globalThis.localStorage = createThrowingStorage();
	try {
		assert.doesNotThrow(() => getPushIntent(), 'getPushIntent swallows the thrown error');
		assert.equal(getPushIntent(), null, 'getPushIntent falls back to null on throw');
		assert.doesNotThrow(() => setPushIntent('user-123'), 'setPushIntent swallows the thrown error');
		assert.doesNotThrow(() => clearPushIntent(), 'clearPushIntent swallows the thrown error');
		assert.doesNotThrow(
			() => setPushIntentOff('user-123'),
			'setPushIntentOff swallows the thrown error'
		);
		assert.doesNotThrow(
			() => hasExplicitPushOptOut('user-123'),
			'hasExplicitPushOptOut swallows the thrown error (via getPushIntent)'
		);
		assert.equal(hasExplicitPushOptOut('user-123'), false, 'falls back to false on throw');
	} finally {
		delete globalThis.localStorage;
	}
});

test('setPushIntentOff/hasExplicitPushOptOut round-trip the opt-out sentinel', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		assert.equal(hasExplicitPushOptOut('user-123'), false, 'starts with no opt-out');

		setPushIntentOff('user-123');
		assert.equal(getPushIntent(), 'off:user-123', 'the sentinel value is off:<userId>');
		assert.equal(hasExplicitPushOptOut('user-123'), true, 'opt-out is now recorded');
	} finally {
		delete globalThis.localStorage;
	}
});

test('hasExplicitPushOptOut is false for a missing marker, another user, or an ON marker', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		assert.equal(hasExplicitPushOptOut('user-123'), false, 'no marker at all');

		setPushIntentOff('user-456');
		assert.equal(
			hasExplicitPushOptOut('user-123'),
			false,
			'another user\'s opt-out must not match'
		);

		setPushIntent('user-123');
		assert.equal(
			hasExplicitPushOptOut('user-123'),
			false,
			'an ON marker for the same user is not an opt-out'
		);
	} finally {
		delete globalThis.localStorage;
	}
});

test('setPushIntent overwrites an existing off sentinel (toggle-ON wins over opt-out)', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		setPushIntentOff('user-123');
		assert.equal(hasExplicitPushOptOut('user-123'), true, 'precondition: opted out');

		setPushIntent('user-123');
		assert.equal(getPushIntent(), 'user-123', 'setPushIntent must overwrite the off sentinel');
		assert.equal(
			hasExplicitPushOptOut('user-123'),
			false,
			'an explicit toggle-ON gesture clears the prior opt-out'
		);
	} finally {
		delete globalThis.localStorage;
	}
});
