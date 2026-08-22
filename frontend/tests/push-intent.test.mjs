import assert from 'node:assert/strict';
import test from 'node:test';

import {
	PUSH_INTENT_KEY,
	PUSH_LOGOUT_GEN_KEY,
	PUSH_LOGOUT_PENDING_KEY,
	PUSH_OPTOUT_KEY,
	backfillPushIntent,
	bumpLogoutGeneration,
	clearLogoutPending,
	clearPushIntent,
	getPushIntent,
	hasExplicitPushOptOut,
	isLogoutPending,
	markLogoutPending,
	readLogoutGeneration,
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

test('PUSH_INTENT_KEY and PUSH_OPTOUT_KEY are distinct, app-prefixed storage keys', () => {
	assert.equal(PUSH_INTENT_KEY, 'jamye:push-intent');
	assert.equal(PUSH_OPTOUT_KEY, 'jamye:push-optout');
	assert.notEqual(PUSH_INTENT_KEY, PUSH_OPTOUT_KEY, 'intent and opt-out must be separate keys');
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

test('the intent key never contains an off: encoding (opt-out lives elsewhere)', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		setPushIntentOff('user-123');
		const raw = localStorage.getItem(PUSH_INTENT_KEY);
		assert.ok(
			raw === null || !raw.startsWith('off:'),
			'opt-out must never be encoded into the intent key value'
		);
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
			'hasExplicitPushOptOut swallows the thrown error'
		);
		assert.equal(hasExplicitPushOptOut('user-123'), false, 'falls back to false on throw');
	} finally {
		delete globalThis.localStorage;
	}
});

test('setPushIntentOff writes the opt-out key and clears the (now stale) intent key', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		setPushIntent('user-123');
		assert.equal(getPushIntent(), 'user-123', 'precondition: intent was ON');

		setPushIntentOff('user-123');
		assert.equal(
			localStorage.getItem(PUSH_OPTOUT_KEY),
			'user-123',
			'the opt-out key stores the user id verbatim'
		);
		assert.equal(getPushIntent(), null, 'the stale intent marker is removed');
		assert.equal(hasExplicitPushOptOut('user-123'), true);
	} finally {
		delete globalThis.localStorage;
	}
});

test('hasExplicitPushOptOut is false for a missing marker, another user, or an ON marker', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		assert.equal(hasExplicitPushOptOut('user-123'), false, 'no marker at all');

		setPushIntentOff('user-456');
		assert.equal(hasExplicitPushOptOut('user-123'), false, "another user's opt-out must not match");

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

test("setPushIntent clears its OWN prior opt-out but never another user's", () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		setPushIntentOff('user-123');
		assert.equal(hasExplicitPushOptOut('user-123'), true, 'precondition: user-123 opted out');

		setPushIntent('user-123');
		assert.equal(getPushIntent(), 'user-123', 'setPushIntent must write the intent key');
		assert.equal(
			hasExplicitPushOptOut('user-123'),
			false,
			"an explicit toggle-ON gesture clears that SAME user's prior opt-out"
		);
	} finally {
		delete globalThis.localStorage;
	}
});

test("setPushIntent for one user never touches a different user's opt-out record", () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		setPushIntentOff('user-456');
		assert.equal(hasExplicitPushOptOut('user-456'), true, 'precondition: user-456 opted out');

		// A backfill-style write for a DIFFERENT user (user-123) must never
		// remove user-456's opt-out record — cross-user writes are the exact
		// hazard the separate key exists to prevent.
		setPushIntent('user-123');
		assert.equal(
			hasExplicitPushOptOut('user-456'),
			true,
			"a different user's setPushIntent must not clear user-456's opt-out"
		);
	} finally {
		delete globalThis.localStorage;
	}
});

test('a backfill-style intent write cannot remove the opt-out key it does not own', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		setPushIntentOff('user-123');
		assert.equal(localStorage.getItem(PUSH_OPTOUT_KEY), 'user-123');

		// Simulate the settings backfill: it only ever calls setPushIntent,
		// never anything that targets PUSH_OPTOUT_KEY directly. Even so, once
		// the SAME user's opt-out is set, only that user's own setPushIntent
		// clears it (previous test) — a structurally separate key means there
		// is no write path that can silently drop it as a side effect of an
		// unrelated key's write.
		localStorage.setItem(PUSH_INTENT_KEY, 'user-999');
		assert.equal(
			localStorage.getItem(PUSH_OPTOUT_KEY),
			'user-123',
			'writing the intent key directly must never disturb the opt-out key'
		);
	} finally {
		delete globalThis.localStorage;
	}
});

test('backfillPushIntent writes intent but never touches an existing opt-out', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		setPushIntentOff('user-123');
		assert.equal(localStorage.getItem(PUSH_OPTOUT_KEY), 'user-123');

		// Unlike setPushIntent (the gesture setter, which clears the same
		// user's opt-out as part of a fresh decision), the backfill setter
		// must leave the opt-out untouched even for the SAME user — it is a
		// non-gesture reconciliation and must never override an explicit off.
		backfillPushIntent('user-123');
		assert.equal(getPushIntent(), 'user-123');
		assert.equal(
			localStorage.getItem(PUSH_OPTOUT_KEY),
			'user-123',
			"the backfill setter must not clear the user's own opt-out record"
		);
	} finally {
		delete globalThis.localStorage;
	}
});

test('backfillPushIntent is a safe no-op without usable storage', () => {
	delete globalThis.localStorage;
	assert.doesNotThrow(() => backfillPushIntent('user-123'));

	globalThis.localStorage = createThrowingStorage();
	try {
		assert.doesNotThrow(() => backfillPushIntent('user-123'));
	} finally {
		delete globalThis.localStorage;
	}
});

test('logout generation round-trips and increments through storage', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		assert.equal(readLogoutGeneration(), '0');
		bumpLogoutGeneration();
		assert.equal(readLogoutGeneration(), '1');
		bumpLogoutGeneration();
		assert.equal(readLogoutGeneration(), '2');
		assert.equal(localStorage.getItem(PUSH_LOGOUT_GEN_KEY), '2');

		// Garbage in storage degrades to 0 and keeps counting from there.
		localStorage.setItem(PUSH_LOGOUT_GEN_KEY, 'not-a-number');
		bumpLogoutGeneration();
		assert.equal(readLogoutGeneration(), '1');
	} finally {
		delete globalThis.localStorage;
	}
});

test('logout generation accessors are safe without usable storage', () => {
	delete globalThis.localStorage;
	assert.equal(readLogoutGeneration(), '0');
	assert.doesNotThrow(() => bumpLogoutGeneration());

	globalThis.localStorage = createThrowingStorage();
	try {
		assert.equal(readLogoutGeneration(), '0');
		assert.doesNotThrow(() => bumpLogoutGeneration());
	} finally {
		delete globalThis.localStorage;
	}
});

test('markLogoutPending/isLogoutPending round-trip: a fresh mark reads as pending', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		assert.equal(isLogoutPending(), false, 'starts empty');
		markLogoutPending();
		assert.equal(isLogoutPending(), true, 'a just-written mark must read as pending');
		assert.ok(
			/^\d+$/.test(localStorage.getItem(PUSH_LOGOUT_PENDING_KEY)),
			'the stored value must be a numeric timestamp'
		);
	} finally {
		delete globalThis.localStorage;
	}
});

test('isLogoutPending expires an old timestamp', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		const old = Date.now() - 60_000;
		localStorage.setItem(PUSH_LOGOUT_PENDING_KEY, String(old));
		assert.equal(isLogoutPending(), false, 'a 60s-old mark must have expired past the 30s default');
		assert.equal(
			isLogoutPending(120_000),
			true,
			'a wider maxAgeMs must still see the same timestamp as pending'
		);
	} finally {
		delete globalThis.localStorage;
	}
});

test('isLogoutPending is false for missing or garbage values, and never throws', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		assert.equal(isLogoutPending(), false, 'no marker at all');
		localStorage.setItem(PUSH_LOGOUT_PENDING_KEY, 'not-a-number');
		assert.doesNotThrow(() => isLogoutPending());
		assert.equal(isLogoutPending(), false, 'garbage must not be treated as pending');
	} finally {
		delete globalThis.localStorage;
	}

	delete globalThis.localStorage;
	assert.equal(isLogoutPending(), false, 'no storage at all');
	assert.doesNotThrow(() => markLogoutPending());
	assert.doesNotThrow(() => clearLogoutPending());

	globalThis.localStorage = createThrowingStorage();
	try {
		assert.equal(isLogoutPending(), false, 'a throwing storage falls back to false');
		assert.doesNotThrow(() => markLogoutPending());
		assert.doesNotThrow(() => clearLogoutPending());
	} finally {
		delete globalThis.localStorage;
	}
});

test('clearLogoutPending removes the marker', () => {
	globalThis.localStorage = createMemoryStorage();
	try {
		markLogoutPending();
		assert.equal(isLogoutPending(), true, 'precondition: marked pending');
		clearLogoutPending();
		assert.equal(isLogoutPending(), false, 'cleared marker must no longer read as pending');
		assert.equal(localStorage.getItem(PUSH_LOGOUT_PENDING_KEY), null);
	} finally {
		delete globalThis.localStorage;
	}
});
