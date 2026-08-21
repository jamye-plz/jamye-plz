/** Room-scoped WebSocket recovery. It deliberately owns no chat data or queries. */
export type ChatConnectionState = 'connecting' | 'connected' | 'disconnected';

export interface ChatSocket {
	readonly readyState: number;
	onopen: ((event: Event) => void) | null;
	onclose: ((event: CloseEvent) => void) | null;
	onerror: ((event: Event) => void) | null;
	onmessage: ((event: MessageEvent) => void) | null;
	send(data: string): void;
	close(): void;
}

export interface ChatSocketTimers {
	setTimeout(callback: () => void, delay: number): ReturnType<typeof setTimeout>;
	clearTimeout(handle: ReturnType<typeof setTimeout>): void;
	setInterval(callback: () => void, delay: number): ReturnType<typeof setInterval>;
	clearInterval(handle: ReturnType<typeof setInterval>): void;
}

export interface ChatSocketEventTarget {
	addEventListener(type: string, listener: EventListener): void;
	removeEventListener(type: string, listener: EventListener): void;
}

interface ChatSocketLifecycleOptions {
	url: string;
	createSocket: (url: string) => ChatSocket;
	onOpen: (socket: ChatSocket) => void;
	onReady: (socket: ChatSocket) => void;
	onMessage: (event: MessageEvent, socket: ChatSocket) => void;
	onTerminalClose: () => void;
	onAuthenticationClose: () => void;
	onSocketChange: (socket: ChatSocket | null) => void;
	onStateChange: (state: ChatConnectionState) => void;
	onRecoveryChange: (recovering: boolean) => void;
	onManualRetryChange: (visible: boolean) => void;
	isOnline: () => boolean;
	isVisible: () => boolean;
	networkEvents: ChatSocketEventTarget;
	visibilityEvents: ChatSocketEventTarget;
	timers?: ChatSocketTimers;
	random?: () => number;
}

export interface ChatSocketLifecycle {
	start(): void;
	retryNow(): void;
	dispose(): void;
	isCurrent(socket: ChatSocket): boolean;
}

interface ReconnectHistoryPage<T extends { id: string }> {
	items: T[];
	next_cursor: string | null;
}

interface ReconnectHistoryOptions<T extends { id: string }> {
	knownIds: ReadonlySet<string>;
	fetchPage(cursor?: string): Promise<ReconnectHistoryPage<T>>;
	applyPage(items: T[]): void;
	isCurrent(): boolean;
}

interface ReconnectHistoryRecoveryOptions<
	T extends { id: string }
> extends ReconnectHistoryOptions<T> {
	timers?: ChatSocketTimers;
	random?: () => number;
	onSuccess?: () => void;
}

export interface ReconnectHistoryRecovery {
	start(): void;
	dispose(): void;
}

/**
 * Walk newest-to-oldest reconnect pages until they overlap the room's existing
 * server history. Scroll pagination keeps its own cursor, so recovery cannot
 * discard previously loaded pages or move the reader's position.
 */
export async function reconcileReconnectHistory<T extends { id: string }>(
	options: ReconnectHistoryOptions<T>
): Promise<void> {
	let cursor: string | undefined;

	while (options.isCurrent()) {
		const page = await options.fetchPage(cursor);
		if (!options.isCurrent()) return;
		options.applyPage(page.items);

		const overlapsExistingHistory =
			options.knownIds.size === 0 || page.items.some((item) => options.knownIds.has(item.id));
		if (
			overlapsExistingHistory ||
			page.items.length === 0 ||
			page.next_cursor === null ||
			page.next_cursor === cursor
		) {
			return;
		}

		cursor = page.next_cursor;
	}
}

const CONNECTING = 0;
const OPEN = 1;
const CLOSING = 2;
const RETRY_BASE_MS = 1_000;
const RETRY_CAP_MS = 30_000;
const CONNECT_DEADLINE_MS = 10_000;
const HEARTBEAT_INTERVAL_MS = 25_000;
const PONG_DEADLINE_MS = 10_000;
const MANUAL_RETRY_AFTER_MS = 30_000;

const browserTimers: ChatSocketTimers = {
	setTimeout: (callback, delay) => setTimeout(callback, delay),
	clearTimeout: (handle) => clearTimeout(handle),
	setInterval: (callback, delay) => setInterval(callback, delay),
	clearInterval: (handle) => clearInterval(handle)
};

function retryDelay(retryNumber: number, random: () => number): number {
	const base = Math.min(RETRY_BASE_MS * 2 ** retryNumber, RETRY_CAP_MS);
	const jitter = Math.floor(random() * RETRY_BASE_MS);
	return Math.min(base + jitter, RETRY_CAP_MS);
}

/**
 * Retries only the REST snapshot that closes one physical socket's join gap.
 * The caller supplies the socket identity guard, so a room switch or replaced
 * socket can neither apply stale pages nor keep a retry timer alive.
 */
export function createReconnectHistoryRecovery<T extends { id: string }>(
	options: ReconnectHistoryRecoveryOptions<T>
): ReconnectHistoryRecovery {
	const timers = options.timers ?? browserTimers;
	const random = options.random ?? Math.random;
	let retryTimer: ReturnType<typeof setTimeout> | null = null;
	let retryNumber = 0;
	let inFlight = false;
	let disposed = false;
	const isActive = () => !disposed && options.isCurrent();

	function clearRetry() {
		if (retryTimer !== null) {
			timers.clearTimeout(retryTimer);
			retryTimer = null;
		}
	}

	function retry() {
		if (!isActive() || retryTimer !== null) return;
		const delay = retryDelay(retryNumber, random);
		retryNumber += 1;
		retryTimer = timers.setTimeout(() => {
			retryTimer = null;
			attempt();
		}, delay);
	}

	function attempt() {
		if (!isActive() || inFlight) return;
		inFlight = true;
		void reconcileReconnectHistory({ ...options, isCurrent: isActive })
			.then(() => {
				if (!isActive()) return;
				retryNumber = 0;
				options.onSuccess?.();
			})
			.catch(() => {
				if (!isActive()) return;
				retry();
			})
			.finally(() => {
				inFlight = false;
			});
	}

	return {
		start() {
			attempt();
		},
		dispose() {
			disposed = true;
			clearRetry();
		}
	};
}

/**
 * Keeps exactly one room socket alive. Browser WebSocket does not expose native
 * ping frames, so JSON ping/pong is used only as liveness evidence here.
 */
export function createChatSocketLifecycle(
	options: ChatSocketLifecycleOptions
): ChatSocketLifecycle {
	const timers = options.timers ?? browserTimers;
	const random = options.random ?? Math.random;
	let socket: ChatSocket | null = null;
	let retryTimer: ReturnType<typeof setTimeout> | null = null;
	let connectDeadline: ReturnType<typeof setTimeout> | null = null;
	let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
	let pongDeadline: ReturnType<typeof setTimeout> | null = null;
	let manualRetryTimer: ReturnType<typeof setTimeout> | null = null;
	let retryNumber = 0;
	let failedSince = false;
	let disposed = false;
	let terminal = false;
	let started = false;
	let waitingForCloseCode = false;

	function setState(state: ChatConnectionState) {
		if (!disposed) options.onStateChange(state);
	}

	function setRecovery(recovering: boolean) {
		if (!disposed) options.onRecoveryChange(recovering);
	}

	function clearRetry() {
		if (retryTimer !== null) {
			timers.clearTimeout(retryTimer);
			retryTimer = null;
		}
	}

	function clearConnectDeadline() {
		if (connectDeadline !== null) {
			timers.clearTimeout(connectDeadline);
			connectDeadline = null;
		}
	}

	function clearHeartbeat() {
		if (heartbeatTimer !== null) {
			timers.clearInterval(heartbeatTimer);
			heartbeatTimer = null;
		}
		if (pongDeadline !== null) {
			timers.clearTimeout(pongDeadline);
			pongDeadline = null;
		}
	}

	function clearManualRetry() {
		if (manualRetryTimer !== null) {
			timers.clearTimeout(manualRetryTimer);
			manualRetryTimer = null;
		}
		options.onManualRetryChange(false);
	}

	function markStable(candidate: ChatSocket) {
		if (socket !== candidate || disposed || terminal) return;
		retryNumber = 0;
		failedSince = false;
		clearManualRetry();
		setState('connected');
		setRecovery(false);
	}

	function detach(candidate: ChatSocket) {
		candidate.onopen = null;
		candidate.onclose = null;
		candidate.onerror = null;
		candidate.onmessage = null;
	}

	function removeRecoveryListeners() {
		options.networkEvents.removeEventListener('online', onOnline);
		options.networkEvents.removeEventListener('offline', onOffline);
		options.visibilityEvents.removeEventListener('visibilitychange', onVisibilityChange);
	}

	function terminate(candidate: ChatSocket, callback: () => void) {
		if (socket !== candidate || disposed || terminal) return;
		terminal = true;
		waitingForCloseCode = false;
		clearRetry();
		clearConnectDeadline();
		clearHeartbeat();
		clearManualRetry();
		removeRecoveryListeners();
		detach(candidate);
		socket = null;
		options.onSocketChange(null);
		setState('disconnected');
		callback();
	}

	function scheduleManualRetry() {
		if (failedSince || terminal || disposed) return;
		failedSince = true;
		manualRetryTimer = timers.setTimeout(() => {
			manualRetryTimer = null;
			if (!disposed && !terminal && failedSince) options.onManualRetryChange(true);
		}, MANUAL_RETRY_AFTER_MS);
	}

	function scheduleRetry() {
		if (disposed || terminal || !options.isOnline() || retryTimer !== null) return;
		const delay = retryDelay(retryNumber, random);
		retryNumber += 1;
		setState('connecting');
		setRecovery(true);
		retryTimer = timers.setTimeout(() => {
			retryTimer = null;
			connect();
		}, delay);
	}

	function retire(candidate: ChatSocket, closeSocket: boolean, immediate = false) {
		if (socket !== candidate || disposed || terminal) return;
		waitingForCloseCode = false;
		clearConnectDeadline();
		clearHeartbeat();
		detach(candidate);
		socket = null;
		options.onSocketChange(null);
		if (closeSocket) {
			try {
				candidate.close();
			} catch {
				// A browser can reject close() while it is already gone. Recovery still proceeds.
			}
		}
		scheduleManualRetry();
		if (!options.isOnline()) {
			setState('disconnected');
			setRecovery(false);
			return;
		}
		if (immediate) {
			setState('connecting');
			setRecovery(true);
			return;
		}
		scheduleRetry();
	}

	function sendHeartbeat(candidate: ChatSocket, recovering = false) {
		if (socket !== candidate || candidate.readyState !== OPEN || pongDeadline !== null) return;
		if (recovering) {
			setState('connecting');
			setRecovery(true);
		}
		try {
			candidate.send(JSON.stringify({ type: 'ping' }));
		} catch {
			retire(candidate, true);
			return;
		}
		pongDeadline = timers.setTimeout(() => {
			pongDeadline = null;
			retire(candidate, true);
		}, PONG_DEADLINE_MS);
	}

	function connect() {
		if (disposed || terminal || !options.isOnline()) {
			if (!disposed && !terminal) {
				setState('disconnected');
				setRecovery(false);
			}
			return;
		}
		if (socket && (socket.readyState === OPEN || socket.readyState === CONNECTING)) return;
		clearRetry();
		setState('connecting');
		setRecovery(failedSince);
		let candidate: ChatSocket;
		try {
			candidate = options.createSocket(options.url);
		} catch {
			scheduleManualRetry();
			scheduleRetry();
			return;
		}
		socket = candidate;
		options.onSocketChange(candidate);
		const deadline = timers.setTimeout(() => {
			if (connectDeadline !== deadline || socket !== candidate) return;
			connectDeadline = null;
			retire(candidate, true);
		}, CONNECT_DEADLINE_MS);
		connectDeadline = deadline;

		candidate.onopen = () => {
			if (socket !== candidate || disposed || terminal) return;
			clearConnectDeadline();
			// A successful transport handshake is not enough: the room still has to
			// pass membership validation and enter ws_hub before sends are safe.
			setState('connecting');
			setRecovery(failedSince);
			heartbeatTimer = timers.setInterval(() => sendHeartbeat(candidate), HEARTBEAT_INTERVAL_MS);
			try {
				options.onOpen(candidate);
			} catch {
				retire(candidate, true);
			}
		};

		candidate.onmessage = (event) => {
			if (socket !== candidate || disposed || terminal) return;
			try {
				const payload = JSON.parse(String(event.data)) as { type?: string };
				if (payload.type === 'pong') {
					if (pongDeadline !== null) {
						timers.clearTimeout(pongDeadline);
						pongDeadline = null;
					}
					markStable(candidate);
					return;
				}
				if (payload.type === 'joined') {
					markStable(candidate);
					try {
						options.onReady(candidate);
					} catch {
						retire(candidate, true);
					}
					return;
				}
			} catch {
				// ChatRoom owns malformed application-frame handling.
			}
			options.onMessage(event, candidate);
		};

		candidate.onerror = () => {
			if (socket !== candidate || disposed || terminal) return;
			// Browser WebSocket errors are paired with a close event. Keep this
			// handler alive until that close supplies its code: 4001 eviction and
			// 1008 authentication failures are terminal; other codes retire below.
			waitingForCloseCode = true;
			// The socket is no longer safe for sends, but its close handler must
			// remain attached until we know whether it was a terminal eviction.
			clearConnectDeadline();
			clearHeartbeat();
			setState('connecting');
			setRecovery(true);
		};
		candidate.onclose = (event) => {
			if (socket !== candidate || disposed || terminal) return;
			if (event.code === 4001) return terminate(candidate, options.onTerminalClose);
			if (event.code === 1008) return terminate(candidate, options.onAuthenticationClose);
			retire(candidate, false);
		};
	}

	function recoverNow() {
		if (disposed || terminal || !options.isOnline()) {
			if (!disposed && !terminal) {
				setState('disconnected');
				setRecovery(false);
			}
			return;
		}
		if (waitingForCloseCode) return;
		clearRetry();
		if (socket?.readyState === OPEN) {
			sendHeartbeat(socket, true);
			return;
		}
		if (socket?.readyState === CONNECTING || socket?.readyState === CLOSING) return;
		if (socket) retire(socket, true, true);
		connect();
	}

	const onOnline = () => recoverNow();
	const onOffline = () => {
		clearRetry();
		setState('disconnected');
		setRecovery(false);
	};
	const onVisibilityChange = () => {
		if (options.isVisible()) recoverNow();
	};

	return {
		start() {
			if (disposed || started) return;
			started = true;
			options.networkEvents.addEventListener('online', onOnline);
			options.networkEvents.addEventListener('offline', onOffline);
			options.visibilityEvents.addEventListener('visibilitychange', onVisibilityChange);
			connect();
		},
		retryNow() {
			if (socket?.readyState === CONNECTING) return;
			recoverNow();
		},
		dispose() {
			if (disposed) return;
			disposed = true;
			clearRetry();
			clearConnectDeadline();
			clearHeartbeat();
			clearManualRetry();
			removeRecoveryListeners();
			if (socket) {
				const current = socket;
				detach(current);
				socket = null;
				try {
					current.close();
				} catch {
					// Nothing else can observe a disposed lifecycle.
				}
			}
		},
		isCurrent(candidate) {
			return !disposed && !terminal && socket === candidate;
		}
	};
}
