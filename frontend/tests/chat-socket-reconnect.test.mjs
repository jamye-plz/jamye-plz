import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
	createReconnectHistoryRecovery,
	createChatSocketLifecycle,
	mergeChatMessageRecords,
	resolveInitialHistoryBoundary,
	reconcileReconnectHistory
} from '../src/lib/chat/chat-socket-lifecycle.ts';

const chatRoomSource = readFileSync(
	new URL('../src/lib/components/ChatRoom.svelte', import.meta.url),
	'utf8'
);

const settlePromises = () => new Promise((resolve) => setImmediate(resolve));

class FakeTimers {
	#now = 0;
	#nextId = 1;
	#tasks = new Map();
	timeoutDelays = [];

	setTimeout = (callback, delay) => {
		this.timeoutDelays.push(delay);
		return this.#add(callback, delay, false);
	};
	clearTimeout = (id) => this.#tasks.delete(id);
	setInterval = (callback, delay) => this.#add(callback, delay, true);
	clearInterval = (id) => this.#tasks.delete(id);

	#add(callback, delay, repeating) {
		const id = this.#nextId++;
		this.#tasks.set(id, { callback, delay, at: this.#now + delay, repeating });
		return id;
	}

	advance(ms) {
		const target = this.#now + ms;
		while (true) {
			const next = [...this.#tasks.entries()]
				.filter(([, task]) => task.at <= target)
				.sort(([, a], [, b]) => a.at - b.at)[0];
			if (!next) break;
			const [id, task] = next;
			this.#now = task.at;
			if (task.repeating) task.at += task.delay;
			else this.#tasks.delete(id);
			task.callback();
		}
		this.#now = target;
	}

	hasPending() {
		return this.#tasks.size > 0;
	}
}

class FakeEvents {
	listeners = new Map();

	addEventListener(type, listener) {
		const listeners = this.listeners.get(type) ?? new Set();
		listeners.add(listener);
		this.listeners.set(type, listeners);
	}

	removeEventListener(type, listener) {
		this.listeners.get(type)?.delete(listener);
	}

	dispatch(type) {
		for (const listener of this.listeners.get(type) ?? []) listener({ type });
	}

	count() {
		return [...this.listeners.values()].reduce((total, listeners) => total + listeners.size, 0);
	}
}

class FakeSocket {
	readyState = 0;
	onopen = null;
	onclose = null;
	onerror = null;
	onmessage = null;
	sent = [];
	closed = false;

	open() {
		this.readyState = 1;
		this.onopen?.({});
	}

	emitError() {
		this.onerror?.({});
	}

	fail(code = 1006) {
		this.emitError();
		this.close(code);
	}

	close(code = 1006) {
		this.readyState = 3;
		this.closed = true;
		this.onclose?.({ code });
	}

	receive(payload) {
		this.onmessage?.({ data: JSON.stringify(payload) });
	}

	send(frame) {
		this.sent.push(JSON.parse(frame));
	}
}

function makeHarness() {
	const timers = new FakeTimers();
	const events = new FakeEvents();
	const sockets = [];
	const states = [];
	const recovery = [];
	const manualRetry = [];
	let online = true;
	let visible = true;
	let readySignals = 0;
	let terminalClosures = 0;
	let authenticationClosures = 0;
	const lifecycle = createChatSocketLifecycle({
		url: 'ws://chat.test/api/ws',
		createSocket: () => {
			const socket = new FakeSocket();
			sockets.push(socket);
			return socket;
		},
		isOnline: () => online,
		isVisible: () => visible,
		networkEvents: events,
		visibilityEvents: events,
		timers,
		random: () => 0.5,
		onOpen: () => {},
		onReady: () => {
			readySignals += 1;
		},
		onMessage: () => {},
		onTerminalClose: () => {
			terminalClosures += 1;
		},
		onAuthenticationClose: () => {
			authenticationClosures += 1;
		},
		onSocketChange: () => {},
		onStateChange: (state) => states.push(state),
		onRecoveryChange: (value) => recovery.push(value),
		onManualRetryChange: (value) => manualRetry.push(value)
	});

	return {
		timers,
		events,
		sockets,
		states,
		recovery,
		manualRetry,
		lifecycle,
		setOnline: (value) => {
			online = value;
		},
		setVisible: (value) => {
			visible = value;
		},
		readySignals: () => readySignals,
		terminalClosures: () => terminalClosures,
		authenticationClosures: () => authenticationClosures
	};
}

test('retry uses 1s exponential base plus bounded jitter, deduplicates error/close, and ignores stale callbacks', () => {
	const h = makeHarness();
	h.lifecycle.start();
	const first = h.sockets[0];
	const staleClose = first.onclose;
	const retryDelays = [1_500, 2_500, 4_500, 8_500, 16_500, 30_000];
	for (const delay of retryDelays) {
		h.sockets.at(-1).fail();
		assert.equal(
			h.timers.timeoutDelays.at(-1),
			delay,
			'backoff must retain its capped jitter bound'
		);
		h.timers.advance(delay);
	}
	assert.equal(h.sockets.length, 7, 'each elapsed delay creates one replacement socket');

	staleClose?.({ code: 1006 });
	h.timers.advance(30_000);
	assert.equal(h.sockets.length, 7, 'an old close callback must not schedule another retry');
	assert.equal(
		h.manualRetry.at(-1),
		true,
		'manual retry becomes visible after continuous recovery failure'
	);
	assert.ok(h.states.includes('connecting'));
	assert.ok(h.recovery.includes(true));
});

test('application readiness gates connected state and resets backoff only after join acknowledgement', () => {
	const h = makeHarness();
	h.lifecycle.start();

	const first = h.sockets[0];
	first.open();
	assert.equal(h.states.at(-1), 'connecting', 'TCP open alone must not enable chat sends');
	first.fail();
	assert.equal(h.timers.timeoutDelays.at(-1), 1_500);
	h.timers.advance(1_500);

	const second = h.sockets[1];
	second.open();
	second.fail();
	assert.equal(
		h.timers.timeoutDelays.at(-1),
		2_500,
		'an open-then-close before join acknowledgement must retain exponential backoff'
	);
	h.timers.advance(2_500);

	const stable = h.sockets[2];
	stable.open();
	stable.receive({ type: 'joined', chatroom_id: 'room-1' });
	assert.equal(h.states.at(-1), 'connected');
	assert.equal(h.readySignals(), 1);
	stable.fail();
	assert.equal(
		h.timers.timeoutDelays.at(-1),
		1_500,
		'a proven application connection resets the next retry to the base delay'
	);
});

test('online and visible resume bypass backoff; pong permits only one outstanding heartbeat', () => {
	const h = makeHarness();
	h.lifecycle.start();
	h.sockets[0].fail();
	h.events.dispatch('online');
	assert.equal(h.sockets.length, 2, 'online must replace a pending retry immediately');
	const socket = h.sockets[1];
	socket.open();

	h.setVisible(false);
	h.events.dispatch('visibilitychange');
	assert.equal(socket.sent.length, 0, 'hidden visibility changes must not probe');
	h.setVisible(true);
	h.events.dispatch('visibilitychange');
	assert.deepEqual(
		socket.sent,
		[{ type: 'ping' }],
		'visible resume probes an open socket immediately'
	);
	h.events.dispatch('online');
	assert.equal(socket.sent.length, 1, 'only one pong deadline may be outstanding');
	socket.receive({ type: 'pong' });
	h.timers.advance(25_000);
	assert.equal(socket.sent.length, 2, 'pong clears the sole deadline for the next heartbeat');
});

test('manual retry, online, and visible recovery leave an active CONNECTING socket alone', () => {
	const h = makeHarness();
	h.lifecycle.start();
	h.sockets[0].fail();
	h.timers.advance(1_500);
	h.timers.advance(28_500);
	assert.equal(h.manualRetry.at(-1), true, 'manual retry is visible after prolonged recovery');
	const connecting = h.sockets.at(-1);
	const socketCountBeforeTriggers = h.sockets.length;

	h.lifecycle.retryNow();
	h.events.dispatch('online');
	h.events.dispatch('visibilitychange');
	assert.equal(
		h.sockets.length,
		socketCountBeforeTriggers,
		'no recovery trigger may replace an active handshake'
	);
	assert.equal(connecting.closed, false, 'the active handshake stays owned by the lifecycle');
});

test('a stalled CONNECTING attempt expires into the normal retry path while an opened socket clears that deadline', () => {
	const stalled = makeHarness();
	stalled.lifecycle.start();
	const first = stalled.sockets[0];
	stalled.timers.advance(10_000);
	assert.equal(first.closed, true, 'a CONNECTING socket must not block recovery forever');
	stalled.timers.advance(1_500);
	assert.equal(
		stalled.sockets.length,
		2,
		'the connect deadline must use the existing backoff retry path'
	);

	const opened = makeHarness();
	opened.lifecycle.start();
	const transportOpen = opened.sockets[0];
	transportOpen.open();
	opened.timers.advance(10_000);
	assert.equal(transportOpen.closed, false, 'onopen must clear the CONNECTING deadline');
});

test('an unanswered heartbeat retires once, while 4001 and disposal suppress all future recovery', () => {
	const h = makeHarness();
	h.lifecycle.start();
	const socket = h.sockets[0];
	socket.open();
	h.timers.advance(25_000);
	assert.deepEqual(socket.sent, [{ type: 'ping' }]);
	h.timers.advance(10_000);
	assert.equal(socket.closed, true, 'heartbeat deadline must retire the current socket');
	h.timers.advance(1_500);
	assert.equal(h.sockets.length, 2, 'retired socket enters the same reconnect path');

	const terminal = h.sockets[1];
	terminal.open();
	terminal.close(4001);
	h.events.dispatch('online');
	h.events.dispatch('visibilitychange');
	h.timers.advance(60_000);
	assert.equal(h.terminalClosures(), 1);
	assert.equal(h.sockets.length, 2, '4001 must never reconnect');

	const errorThenEviction = makeHarness();
	errorThenEviction.lifecycle.start();
	const errored = errorThenEviction.sockets[0];
	errored.open();
	errorThenEviction.timers.advance(25_000);
	assert.deepEqual(
		errored.sent,
		[{ type: 'ping' }],
		'the test starts with an outstanding heartbeat'
	);
	assert.equal(
		errorThenEviction.timers.hasPending(),
		true,
		'heartbeat deadline is armed before error'
	);
	errored.emitError();
	assert.equal(
		errorThenEviction.states.at(-1),
		'connecting',
		'error must immediately make sending unsafe'
	);
	assert.equal(
		errorThenEviction.recovery.at(-1),
		true,
		'error enters visible recovery while waiting for close'
	);
	assert.equal(
		errorThenEviction.timers.hasPending(),
		false,
		'error clears heartbeat interval and pong deadline'
	);
	assert.equal(errorThenEviction.sockets.length, 1, 'error waits for the paired close code');
	errorThenEviction.events.dispatch('online');
	errorThenEviction.events.dispatch('visibilitychange');
	assert.equal(
		errorThenEviction.sockets.length,
		1,
		'resume triggers must not replace a socket before its paired close code arrives'
	);
	assert.equal(
		errored.sent.length,
		1,
		'resume triggers must not probe while a close code is pending'
	);
	errorThenEviction.timers.advance(10_000);
	assert.equal(
		errorThenEviction.sockets.length,
		1,
		'cleared heartbeat deadline cannot retire or replace the errored socket'
	);
	errored.close(4001);
	errorThenEviction.events.dispatch('online');
	errorThenEviction.timers.advance(60_000);
	assert.equal(errorThenEviction.terminalClosures(), 1, 'error followed by 4001 remains terminal');
	assert.equal(
		errorThenEviction.sockets.length,
		1,
		'error then 4001 must not schedule a replacement'
	);
	assert.equal(errorThenEviction.timers.hasPending(), false, 'terminal cleanup clears every timer');

	const clean = makeHarness();
	clean.lifecycle.start();
	clean.sockets[0].open();
	clean.lifecycle.dispose();
	assert.equal(clean.events.count(), 0, 'dispose removes online/offline/visibility listeners');
	assert.equal(
		clean.timers.hasPending(),
		false,
		'dispose clears retry, heartbeat, deadline, and manual timers'
	);
	clean.events.dispatch('online');
	clean.timers.advance(60_000);
	assert.equal(clean.sockets.length, 1, 'dispose leaves no zombie reconnect loop');
});

test('1008 is terminal authentication failure even after error, with no successor or retained work', () => {
	const h = makeHarness();
	h.lifecycle.start();
	const socket = h.sockets[0];
	socket.open();
	socket.receive({ type: 'joined', chatroom_id: 'room-1' });
	h.timers.advance(25_000);
	assert.deepEqual(socket.sent, [{ type: 'ping' }], 'the test starts with active heartbeat work');

	socket.fail(1008);
	assert.equal(h.authenticationClosures(), 1, '1008 must use only the authentication callback');
	assert.equal(h.terminalClosures(), 0, '1008 must not use the eviction callback');
	assert.equal(h.events.count(), 0, 'terminal auth removes recovery event listeners');
	assert.equal(
		h.timers.hasPending(),
		false,
		'1008 clears retry, connect, heartbeat, and manual timers'
	);
	h.events.dispatch('online');
	h.events.dispatch('visibilitychange');
	h.timers.advance(60_000);
	assert.equal(h.sockets.length, 1, '1008 must never create a successor socket');
});

test('reconnect history paginates backward until it overlaps local history', async () => {
	const requestedCursors = [];
	const appliedIds = [];
	const items = (newest, oldest) =>
		Array.from({ length: newest - oldest + 1 }, (_, index) => ({ id: `m${newest - index}` }));

	await reconcileReconnectHistory({
		knownIds: new Set(['m100']),
		fetchPage: async (cursor) => {
			requestedCursors.push(cursor ?? null);
			if (cursor === undefined) {
				return { items: items(170, 121), next_cursor: 'before-m121' };
			}
			if (cursor === 'before-m121') {
				return { items: items(120, 71), next_cursor: 'before-m71' };
			}
			throw new Error(`unexpected cursor: ${cursor}`);
		},
		applyPage: (pageItems) => appliedIds.push(...pageItems.map((item) => item.id)),
		isCurrent: () => true
	});

	assert.deepEqual(
		requestedCursors,
		[null, 'before-m121'],
		'a 70-message interruption requires the second page but stops at the known overlap'
	);
	assert.equal(appliedIds.length, 100);
	for (let id = 101; id <= 170; id += 1) {
		assert.ok(appliedIds.includes(`m${id}`), `missed message m${id} must be recovered`);
	}
});

test('empty known history on a real reconnect continues across every available page', async () => {
	const requestedCursors = [];
	const appliedIds = [];
	const page = (newest, oldest, next_cursor) => ({
		items: Array.from({ length: newest - oldest + 1 }, (_, index) => ({
			id: `m${newest - index}`
		})),
		next_cursor
	});

	await reconcileReconnectHistory({
		knownIds: new Set(),
		fetchPage: async (cursor) => {
			requestedCursors.push(cursor ?? null);
			return cursor === undefined ? page(120, 71, 'before-m71') : page(70, 21, null);
		},
		applyPage: (items) => appliedIds.push(...items.map((item) => item.id)),
		isCurrent: () => true
	});

	assert.deepEqual(requestedCursors, [null, 'before-m71']);
	assert.equal(
		appliedIds.length,
		100,
		'an outage with more than 50 missed messages must recover all pages'
	);
	assert.ok(appliedIds.includes('m21'));
});

test('initial query seed merges with joined WS and recovery records instead of replacing them', () => {
	const merged = mergeChatMessageRecords(
		[
			{ id: 'ws-live', created_at: '2026-08-22T10:02:00Z' },
			{
				id: 'optimistic-client-1',
				client_msg_id: 'client-1',
				pending: true,
				created_at: '2026-08-22T10:03:00Z'
			}
		],
		[
			{ id: 'seed-old', created_at: '2026-08-22T10:01:00Z' },
			{
				id: 'server-client-1',
				client_msg_id: 'client-1',
				created_at: '2026-08-22T10:03:00Z'
			}
		],
		(a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)
	);

	assert.deepEqual(
		merged.map((message) => message.id),
		['seed-old', 'ws-live', 'server-client-1'],
		'late initial query data must retain WS/recovery records and reconcile only its matching optimistic row'
	);
});

test('initial history boundary prefers cached empty data over a later in-flight page', async () => {
	const boundary = await resolveInitialHistoryBoundary({
		knownIds: new Set(),
		cachedPage: { items: [], next_cursor: null },
		inFlightPage: new Promise(() => {}),
		isCurrent: () => true
	});

	assert.deepEqual(
		[...boundary],
		[],
		'a successful pre-subscription empty snapshot is a valid boundary'
	);
});

test('initial history boundary consumes only an existing in-flight page when cache is absent', async () => {
	let resolvePage;
	const appliedIds = [];
	const inFlightPage = new Promise((resolve) => {
		resolvePage = resolve;
	});
	const boundaryPromise = resolveInitialHistoryBoundary({
		knownIds: new Set(),
		inFlightPage,
		isCurrent: () => true,
		applyPage: (items) => appliedIds.push(...items.map((item) => item.id))
	});
	resolvePage({ items: [{ id: 'pre-subscription' }], next_cursor: null });

	const boundary = await boundaryPromise;
	assert.deepEqual([...boundary], ['pre-subscription']);
	assert.deepEqual(appliedIds, ['pre-subscription']);
});

test('initial history boundary falls back to uncapped empty boundary on rejected or absent in-flight work', async () => {
	const rejected = await resolveInitialHistoryBoundary({
		knownIds: new Set(),
		inFlightPage: Promise.reject(new Error('initial page failed')),
		isCurrent: () => true
	});
	const absent = await resolveInitialHistoryBoundary({
		knownIds: new Set(),
		isCurrent: () => true
	});

	assert.deepEqual([...rejected], []);
	assert.deepEqual([...absent], []);
});

test('initial history boundary returns a captured local boundary without touching cache work', async () => {
	const boundary = await resolveInitialHistoryBoundary({
		knownIds: new Set(['already-rendered']),
		inFlightPage: new Promise(() => {}),
		isCurrent: () => true
	});

	assert.deepEqual([...boundary], ['already-rendered']);
});

test('reconnect history recovery retries transient failures on the same current socket and cancels cleanly', async () => {
	const timers = new FakeTimers();
	const appliedIds = [];
	let attempts = 0;
	let current = true;
	const recovery = createReconnectHistoryRecovery({
		knownIds: new Set(['m1']),
		fetchPage: async () => {
			attempts += 1;
			if (attempts === 1) throw new Error('temporary history failure');
			return { items: [{ id: 'm2' }, { id: 'm1' }], next_cursor: null };
		},
		applyPage: (items) => appliedIds.push(...items.map((item) => item.id)),
		isCurrent: () => current,
		timers,
		random: () => 0.5
	});

	recovery.start();
	await settlePromises();
	assert.equal(
		timers.timeoutDelays.at(-1),
		1_500,
		'first recovery retry uses shared 1s+jitter backoff'
	);
	recovery.dispose();
	timers.advance(60_000);
	assert.equal(
		attempts,
		1,
		'disposing a pending retry must not refetch while its socket is still current'
	);

	const succeedingRecovery = createReconnectHistoryRecovery({
		knownIds: new Set(['m1']),
		fetchPage: async () => {
			attempts += 1;
			return { items: [{ id: 'm2' }, { id: 'm1' }], next_cursor: null };
		},
		applyPage: (items) => appliedIds.push(...items.map((item) => item.id)),
		isCurrent: () => current,
		timers,
		random: () => 0.5
	});

	succeedingRecovery.start();
	await settlePromises();
	assert.equal(attempts, 2, 'a replacement controller retries on the same healthy physical socket');
	assert.deepEqual(appliedIds, ['m2', 'm1'], 'the successful retry uses the original merge path');

	current = false;
	succeedingRecovery.dispose();
	timers.advance(60_000);
	assert.equal(attempts, 2, 'room replacement/disposal cancels any future history retry');
});

test('disposing an in-flight reconnect history recovery prevents stale merge and success callbacks', async () => {
	let resolveFetch;
	const appliedIds = [];
	let successes = 0;
	const recovery = createReconnectHistoryRecovery({
		knownIds: new Set(),
		fetchPage: () =>
			new Promise((resolve) => {
				resolveFetch = resolve;
			}),
		applyPage: (items) => appliedIds.push(...items.map((item) => item.id)),
		isCurrent: () => true,
		onSuccess: () => {
			successes += 1;
		}
	});

	recovery.start();
	recovery.dispose();
	resolveFetch({ items: [{ id: 'stale' }], next_cursor: null });
	await settlePromises();
	assert.deepEqual(appliedIds, [], 'a disposed controller must not merge a late page');
	assert.equal(successes, 0, 'a disposed controller must not run its follow-up success action');
});

test('ChatRoom only queues sends after liveness and reconciles fetched client message ids', () => {
	const sendMessage = chatRoomSource.match(/function sendMessage[\s\S]*?\n\t}/)?.[0];
	assert.ok(sendMessage, 'ChatRoom must retain its sendMessage implementation');
	assert.match(
		sendMessage,
		/connectionState !== 'connected'/,
		'a resume heartbeat probe must not let an upload discard its draft'
	);
	assert.match(
		chatRoomSource,
		/mergeChatMessageRecords\([\s\S]*pageItems\.map\(applyBufferedTranscripts\)[\s\S]*compareMessages/,
		'join-gap records must use the common optimistic-safe merge path'
	);
	assert.match(
		chatRoomSource,
		/const hasNewRecoveryMessages = pageItems\.some\(\(message\) => !existingIds\.has\(message\.id\)\)[\s\S]*if \(stick && hasNewRecoveryMessages\)[\s\S]*tick\(\)\.then\(\(\) => \{[\s\S]*if \(!lifecycle\.isCurrent\(socket\)\) return;[\s\S]*scrollToBottom\(\)[\s\S]*document\.visibilityState === 'visible'[\s\S]*tryMarkRead\(\)/,
		'a current visible reader at the bottom must mark genuinely recovered messages as read after scrolling'
	);
	assert.match(
		chatRoomSource,
		/onOpen: \(socket\) => \{[\s\S]*type: 'join'[\s\S]*\},[\s\S]*onReady: \(socket\) => \{[\s\S]*startHistoryRecovery\(socket, recoveryKnownIds\)/,
		'ChatRoom must start reconnect history recovery only after join acknowledgement'
	);
	assert.match(
		chatRoomSource,
		/let hasJoinedSocket = false;[\s\S]*const isInitialRoomJoin = !hasJoinedSocket;[\s\S]*hasJoinedSocket = true;[\s\S]*if \(isInitialRoomJoin\) \{[\s\S]*void startInitialHistoryRecovery\(socket, recoveryKnownIds\);[\s\S]*return;\s*\}/,
		'only the first joined socket may await the current initial-query recovery boundary'
	);
	assert.match(
		chatRoomSource,
		/async function startInitialHistoryRecovery\(\s*socket: ChatSocket,\s*recoveryBoundaryIds: ReadonlySet<string>\s*\)[\s\S]*queryClient\.getQueryData<ChatPage>\(\['messages', roomId\]\)[\s\S]*getQueryCache\(\)\.find<ChatPage>\(\{\s*queryKey: \['messages', roomId\],\s*exact: true\s*\}\)[\s\S]*resolveInitialHistoryBoundary\(\{[\s\S]*knownIds: recoveryBoundaryIds[\s\S]*isCurrent: \(\) => isRoomSocketCurrent\(socket\)/,
		'first join must use only exact-key cached or existing in-flight pre-subscription query work'
	);
	assert.doesNotMatch(
		chatRoomSource,
		/messagesQuery\.refetch/,
		'initial boundary recovery must never start a fresh query refetch'
	);
	const roomResetStart = chatRoomSource.indexOf('let activeRoomKey');
	const roomSeedStart = chatRoomSource.indexOf('// Seed the room from the latest page');
	const socketEffectStart = chatRoomSource.indexOf('$effect(() => {\n\t\tif (!chatroomId) return;');
	const socketEffectEnd = chatRoomSource.indexOf(
		'\n\t// True when the viewport is at/near the newest message',
		socketEffectStart
	);
	assert.ok(
		roomResetStart >= 0 && roomResetStart < roomSeedStart,
		'room-switch reset must be registered before cached query data can seed the new room'
	);
	assert.match(
		chatRoomSource,
		/let activeRoomKey = ''[\s\S]*const roomKey = `\$\{groupId\}:\$\{chatroomId\}`;[\s\S]*roomKey === activeRoomKey[\s\S]*untrack\(\(\) => \{[\s\S]*messages = \[\];[\s\S]*nextCursor = null;[\s\S]*loadingOlder = false;[\s\S]*initialReady = false;[\s\S]*clearTimeout\(pendingRead\)[\s\S]*lastReadAt = Number\.NEGATIVE_INFINITY;[\s\S]*pendingTranscripts\.clear\(\)[\s\S]*historyRecoveryPending = true/,
		'only a new room key may reset message, paging, read, transcript, and recovery state'
	);
	assert.doesNotMatch(
		chatRoomSource.slice(socketEffectStart, socketEffectEnd),
		/pendingRead|lastReadAt|messages = \[\]|nextCursor = null|pendingTranscripts\.clear/,
		'the socket lifecycle effect must not react to read-throttle or room-reset state'
	);
	const seedEffectStart = chatRoomSource.indexOf(
		'$effect(() => {\n\t\tconst seedPage = messagesQuery.data;'
	);
	const seedEffectEnd = chatRoomSource.indexOf('\n\n\tfunction compareMessages', seedEffectStart);
	assert.ok(seedEffectStart >= 0, 'query seed effect must name its reactive page input');
	assert.match(
		chatRoomSource.slice(seedEffectStart, seedEffectEnd),
		/seedPage\.items\.filter\(\s*\(message\) => message\.chatroom_id === chatroomId\s*\)[\s\S]*untrack\(\(\) =>[\s\S]*applyBufferedTranscripts[\s\S]*untrack\(\(\) => mergeChatMessageRecords\(messages, seededMessages, compareMessages\)[\s\S]*untrack\(\(\) => tryMarkRead\(newest \?\? createdAt\)\)/,
		'query seed must untrack transcript, current-message, and read-throttle state'
	);
	assert.match(
		chatRoomSource,
		/messages\s*\.filter\(\(message\) => !message\.pending && message\.chatroom_id === roomId\)/,
		'join snapshots must never seed new-room recovery with old-room message ids'
	);
	assert.match(
		chatRoomSource,
		/const requestRoomId = chatroomId;[\s\S]*await listMessages\(requestGroupId, requestRoomId, cursor\);[\s\S]*if \(chatroomId !== requestRoomId \|\| groupId !== requestGroupId\) return;/,
		'a stale load-older response must not write into a newly selected room'
	);
	assert.match(
		chatRoomSource,
		/createReconnectHistoryRecovery(?:<ChatMessage>)?\([\s\S]*onSuccess:[\s\S]*historyRecoveryPending = false/,
		'ChatRoom must own a cancellable retry chain for transient join-gap history failures'
	);
	assert.match(
		chatRoomSource,
		/function tryMarkRead\(explicitUpTo\?: string\) \{[\s\S]*historyRecoveryPending[\s\S]*onSuccess:[\s\S]*historyRecoveryPending = false[\s\S]*tryMarkRead\(\)/,
		'read receipts must wait for successful gap recovery, then advance only from the current recovery path'
	);
	assert.match(
		chatRoomSource,
		/onAuthenticationClose: \(\) => \{[\s\S]*queryClient\.clear\(\)[\s\S]*window\.location\.assign\('\/login'\)/,
		'1008 must clear stale query state and use a hard login redirect, separately from eviction'
	);
	assert.match(
		chatRoomSource,
		/role="status"/,
		'the connection indicator must expose status semantics'
	);
	assert.match(chatRoomSource, /aria-live="polite"/, 'connection changes must be announced');
	assert.match(
		chatRoomSource,
		/class="(?=[^"]*\bstatus\b)(?=[^"]*\bstatus-success\b)(?=[^"]*\bstatus-xl\b)[^"]*"/,
		'the connected beacon must retain its status, success, and size classes in any order'
	);
	assert.match(chatRoomSource, /<Check\b/, 'the connected beacon must include a non-color cue');
	assert.match(
		chatRoomSource,
		/<span class:sr-only=\{connectionState === 'connected'\}>\{connectionLabel\}<\/span>/,
		'the connected label must remain available to screen readers'
	);
	assert.match(
		chatRoomSource,
		/const manualRetryDisabled = \$derived\([\s\S]*retryAttemptActive \|\| connectionState === 'disconnected'[\s\S]*disabled=\{manualRetryDisabled\}/,
		'the retry control must be inert both offline and during an active handshake'
	);
	assert.match(
		chatRoomSource,
		/data-chat-retry="header"[\s\S]*class="[^"]*hidden[^"]*sm:inline-flex[^"]*"/,
		'the one-line header retry control must be absent at phone widths'
	);
	assert.match(
		chatRoomSource,
		/data-chat-retry-row[\s\S]*class="[^"]*sm:hidden[^"]*"[\s\S]*data-chat-retry="mobile"/,
		'the phone retry control must use its own responsive row below the header'
	);
});
