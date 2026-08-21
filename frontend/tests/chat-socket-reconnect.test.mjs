import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { createChatSocketLifecycle } from '../src/lib/chat/chat-socket-lifecycle.ts';

const chatRoomSource = readFileSync(
	new URL('../src/lib/components/ChatRoom.svelte', import.meta.url),
	'utf8'
);

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
	let terminalClosures = 0;
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
		onMessage: () => {},
		onTerminalClose: () => {
			terminalClosures += 1;
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
		terminalClosures: () => terminalClosures
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
	const connecting = h.sockets[1];
	h.timers.advance(28_500);
	assert.equal(h.manualRetry.at(-1), true, 'manual retry is visible after prolonged recovery');

	h.lifecycle.retryNow();
	h.events.dispatch('online');
	h.events.dispatch('visibilitychange');
	assert.equal(h.sockets.length, 2, 'no recovery trigger may replace an active handshake');
	assert.equal(connecting.closed, false, 'the active handshake stays owned by the lifecycle');
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
		/message\.client_msg_id[\s\S]*candidate\.pending && candidate\.client_msg_id === message\.client_msg_id[\s\S]*combined\.delete\(optimistic\.id\)/,
		'a fetched canonical message must replace its matching optimistic row'
	);
	assert.match(
		chatRoomSource,
		/role="status" aria-live="polite" class="flex items-center gap-1 text-xs whitespace-nowrap"[\s\S]*status status-success status-xl[\s\S]*<Check[\s\S]*<span class:sr-only=\{connectionState === 'connected'\}>\{connectionLabel\}<\/span>/,
		'the connected state must use a non-color check beacon with a screen-reader-only label'
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
