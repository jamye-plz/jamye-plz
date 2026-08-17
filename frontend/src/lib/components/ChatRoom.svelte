<script lang="ts">
	import { tick, untrack } from 'svelte';
	import { SvelteMap, SvelteSet } from 'svelte/reactivity';
	import { createQuery, useQueryClient } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { listMessages, markChatroomRead, refreshChatMediaUrl } from '$lib/api/chat.api';
	import { renderMarkdown } from '$lib/markdown';
	import { getMe } from '$lib/api/auth.api';
	import type {
		ChatMedia,
		ChatMediaInput,
		ChatMessage,
		WsClientMessage,
		WsServerMessage
	} from '$lib/types/chat.types';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import Pencil from '@lucide/svelte/icons/pencil';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import ChatComposer from '$lib/components/ChatComposer.svelte';
	import MessageMedia from '$lib/components/MessageMedia.svelte';
	import MediaLightbox from '$lib/components/MediaLightbox.svelte';

	// A single chatroom view (history + live WS + composer). Reused by the group
	// main chat and per-topic chat — each is an isolated room keyed by chatroomId.
	let {
		groupId,
		chatroomId,
		title,
		backHref,
		pinnedBody,
		canEditPinned = false,
		onEditPinned,
		canRenameTitle = false,
		onRenameTitle,
		createdAt
	}: {
		groupId: string;
		chatroomId: string;
		title: string;
		backHref: string;
		pinnedBody?: string | null;
		canEditPinned?: boolean;
		onEditPinned?: () => void;
		canRenameTitle?: boolean;
		onRenameTitle?: () => void;
		/** Room (topic/chatroom) creation time — the read bound for an empty room. */
		createdAt?: string;
	} = $props();

	const queryClient = useQueryClient();

	// Matches ws_hub.EVICTED_CLOSE_CODE on the backend: the server closes a
	// socket with this code when the user is removed from / the group is deleted.
	const EVICTED_CLOSE_CODE = 4001;

	// backHref is a caller-provided absolute app route (may carry a ?date query).
	// resolve()'s typed-routes signature only accepts statically-known route
	// literals, not a runtime string, so navigate directly.
	function goBack() {
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- backHref is a caller-provided absolute app route
		goto(backHref);
	}

	// Throttle mark-read network calls, but coalesce a trailing call so the LAST
	// visible message in a burst still clears the unread state. Dropping the read
	// outright would leave a phantom unread dot/notification for a message the
	// user is actively viewing (the server now creates the notification before
	// broadcasting), until a later message or a re-entry.
	// -Infinity so the FIRST read always fires immediately (even on a fresh deep-link
	// load where performance.now() is still < 1500ms); only later calls throttle.
	let lastReadAt = Number.NEGATIVE_INFINITY;
	let pendingRead: ReturnType<typeof setTimeout> | null = null;

	function tryMarkRead(explicitUpTo?: string) {
		if (!groupId || !chatroomId) return;
		const since = performance.now() - lastReadAt;
		if (since < 1500) {
			// Within the window: ensure exactly one trailing read fires after it.
			if (pendingRead === null) {
				pendingRead = setTimeout(() => {
					pendingRead = null;
					tryMarkRead();
				}, 1500 - since);
			}
			return;
		}
		lastReadAt = performance.now();
		// Bind the receipt to the newest message we actually have, so a message
		// that slipped through the history/WS entry gap isn't marked read unseen.
		// For an empty room, bound to the room's creation time (not server-now) so
		// a first message landing in the entry gap stays unread. Callers inside a
		// reactive $effect pass `explicitUpTo` so reading `messages` here doesn't
		// make `messages` a dependency of that effect.
		const upTo =
			explicitUpTo ?? (messages.length ? messages[messages.length - 1].created_at : createdAt);
		markChatroomRead(groupId, chatroomId, upTo)
			.then(() => {
				queryClient.invalidateQueries({ queryKey: ['notifications'] });
				queryClient.invalidateQueries({ queryKey: ['topics', groupId] });
			})
			.catch(() => {
				// swallow — must not disrupt chat
			});
	}

	// Cancel any pending trailing read when the room is torn down.
	$effect(() => () => {
		if (pendingRead !== null) clearTimeout(pendingRead);
	});

	// A message that arrived while the tab was hidden didn't send a read receipt;
	// mark read when the tab becomes visible again so it doesn't stay unread.
	$effect(() => {
		function onVisibility() {
			if (document.visibilityState === 'visible') tryMarkRead();
		}
		document.addEventListener('visibilitychange', onVisibility);
		return () => document.removeEventListener('visibilitychange', onVisibility);
	});

	const meQuery = createQuery(() => ({ queryKey: ['me'], queryFn: getMe }));
	const myId = $derived(meQuery.data?.id ?? null);

	// My messages: optimistic placeholders (sender_id null) and acknowledged /
	// reloaded ones (sender_id === my id).
	function isMine(msg: ChatMessage): boolean {
		return msg.sender_id === null || msg.sender_id === myId;
	}

	const messagesQuery = createQuery(() => ({
		queryKey: ['messages', chatroomId],
		queryFn: () =>
			chatroomId
				? listMessages(groupId, chatroomId)
				: Promise.resolve({ items: [], next_cursor: null }),
		enabled: !!chatroomId,
		// Live messages arrive over WS into local state, not this cache, so a
		// cached page goes stale the moment anyone sends a message. Always refetch
		// when re-entering a room so the history reflects the latest server state
		// (otherwise a just-sent message is missing until a hard refresh).
		staleTime: 0,
		refetchOnMount: 'always',
		// Liveness comes from the WS; an auto-refetch mid-session would reset the
		// local `messages` array (dropping older pages loaded by scroll-up and the
		// user's scroll position), so don't refetch on focus/reconnect.
		refetchOnWindowFocus: false,
		refetchOnReconnect: false
	}));

	let messages = $state<ChatMessage[]>([]);
	// Keyset cursor for paging OLDER history (null = no more / not loaded yet).
	let nextCursor = $state<string | null>(null);
	let loadingOlder = $state(false);
	// Hide the list until the first page is pinned to the bottom, so entering a
	// room never flashes at the oldest message before jumping to the newest.
	let initialReady = $state(false);
	let ws = $state<WebSocket | null>(null);
	let connected = $state(false);
	let messagesEl = $state<HTMLElement | null>(null);
	let rootEl = $state<HTMLElement | null>(null);
	// True while the on-screen keyboard is open — drops the composer's home-indicator
	// bottom inset so the input sits flush on the keyboard (no gap) while it's up.
	let keyboardOpen = $state(false);
	// Topic body (pinned) is collapsed by default and revealed only via the header
	// chevron. Reset the toggle when switching to a different room/topic so a body
	// left open on one topic doesn't auto-open on the next.
	let bodyOpen = $state(false);
	let bodyOpenRoom = '';
	$effect(() => {
		if (chatroomId !== bodyOpenRoom) {
			bodyOpenRoom = chatroomId;
			bodyOpen = false;
		}
	});

	// Keep the header pinned while the on-screen keyboard is open — only the messages +
	// composer occupy the area above the keyboard (KakaoTalk-style). BEST-EFFORT: this
	// is a documented WebKit limitation, not a fully solvable problem in a PWA. iOS
	// reveals a focused input by PANNING the visual viewport (dragging even
	// `position:fixed` elements up), and it fires NO per-frame visualViewport events
	// during the keyboard animation — only the settled value. So the SETTLED (fully
	// open/closed) state is correct, but the open/close transition still shows iOS's own
	// slide, which JS cannot intercept. `env(keyboard-inset-height)` would be cleaner but
	// Safari/WebKit does not support it; a native shell (Capacitor) is the only complete fix.
	//
	// Mechanism: pin the whole document (body position:fixed) so iOS never scrolls the
	// window (that scroll used to fight our reset in a feedback loop), then, on each
	// visualViewport change, size the fixed root to `visualViewport.height` and translate
	// it back down by `visualViewport.offsetTop` (GPU transform, frame-accurate) to cancel
	// the pan — so at rest the header sits at the visible top and the composer above the keyboard.
	$effect(() => {
		if (typeof window === 'undefined' || !window.visualViewport || !rootEl) return;

		const vv = window.visualViewport;
		const root = rootEl;
		const docEl = document.documentElement;
		const body = document.body;
		const prev = {
			htmlOverflow: docEl.style.overflow,
			bodyOverflow: body.style.overflow,
			bodyPosition: body.style.position,
			bodyInset: body.style.inset,
			bodyWidth: body.style.width
		};
		// Fully immobilise the document so iOS never scrolls the window — otherwise
		// window.scrollY drifts and fights any reset in a feedback loop (the values
		// "count" and the page rises from the bottom). With the document pinned, the
		// only remaining motion is the visual-viewport pan, which the transform cancels.
		docEl.style.overflow = 'hidden';
		body.style.overflow = 'hidden';
		body.style.position = 'fixed';
		body.style.inset = '0';
		body.style.width = '100%';

		let baseWidth = window.innerWidth;
		let fullHeight = window.innerHeight;
		function apply() {
			// On an orientation/layout flip the viewport WIDTH changes; rebase the height
			// reference so the taller portrait max isn't mistaken for an open keyboard in
			// landscape (which would wrongly drop the composer's safe-area bottom inset).
			if (window.innerWidth !== baseWidth) {
				baseWidth = window.innerWidth;
				fullHeight = window.innerHeight;
			}
			fullHeight = Math.max(fullHeight, window.innerHeight);
			keyboardOpen = fullHeight - vv.height > 100;
			const stick = isNearBottom();
			root.style.height = `${vv.height}px`;
			root.style.transform = `translateY(${vv.offsetTop}px)`;
			if (stick) requestAnimationFrame(scrollToBottom);
		}
		apply();

		vv.addEventListener('resize', apply);
		vv.addEventListener('scroll', apply);

		return () => {
			vv.removeEventListener('resize', apply);
			vv.removeEventListener('scroll', apply);
			root.style.height = '';
			root.style.transform = '';
			docEl.style.overflow = prev.htmlOverflow;
			body.style.overflow = prev.bodyOverflow;
			body.style.position = prev.bodyPosition;
			body.style.inset = prev.bodyInset;
			body.style.width = prev.bodyWidth;
		};
	});

	// Seed the room from the latest page (newest-first → reversed to oldest-first
	// for display) and remember the cursor to older history. Mid-session refetch
	// is disabled, so this only runs on entry — then WS + loadOlder own `messages`.
	$effect(() => {
		if (messagesQuery.data) {
			messages = [...messagesQuery.data.items].reverse().map(applyBufferedTranscripts);
			nextCursor = messagesQuery.data.next_cursor;
			// Pin to the bottom before revealing: scroll after the DOM updates
			// (tick) and again after layout settles (rAF), then show the list.
			tick().then(() => {
				scrollToBottom();
				requestAnimationFrame(() => {
					scrollToBottom();
					initialReady = true;
				});
			});
			// Mark the room read on entry, bounded to the fetched page's newest
			// message read from messagesQuery.data (NOT the reactive `messages`), so
			// this effect doesn't depend on `messages` and re-seed it — dropping live
			// messages / older pages — when it later changes.
			const newest = messagesQuery.data.items[0]?.created_at;
			tryMarkRead(newest ?? untrack(() => createdAt));
		}
	});

	$effect(() => {
		if (!chatroomId) return;

		const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
		const socket = new WebSocket(`${protocol}://${window.location.host}/api/ws`);

		socket.onopen = () => {
			connected = true;
			const joinMsg: WsClientMessage = {
				type: 'join',
				chatroom_id: chatroomId
			};
			socket.send(JSON.stringify(joinMsg));
			// Close the REST/WS gap: a message can arrive between the history fetch
			// and this join (so it's in neither the fetched page nor the broadcast).
			// Re-fetch the latest page and merge anything we don't have, keeping the
			// stream contiguous before a read can advance past it.
			listMessages(groupId, chatroomId)
				.then((page) => {
					const have = new Set(messages.map((m) => m.id));
					const missed = page.items.filter((m) => !have.has(m.id)).map(applyBufferedTranscripts);
					if (!missed.length) return;
					const stick = isNearBottom();
					messages = [...messages, ...missed].sort((a, b) =>
						a.created_at < b.created_at
							? -1
							: a.created_at > b.created_at
								? 1
								: a.id.localeCompare(b.id)
					);
					if (stick) tick().then(scrollToBottom);
				})
				.catch(() => {
					// transient — the next live message / re-entry will reconcile
				});
		};

		socket.onmessage = (event) => {
			try {
				const data: WsServerMessage = JSON.parse(event.data as string);
				const stick = isNearBottom();
				if (data.type === 'message') {
					const msg: ChatMessage = applyBufferedTranscripts({
						id: data.id,
						chatroom_id: data.chatroom_id,
						sender_id: data.sender_id,
						sender_nickname: data.sender_nickname ?? undefined,
						sender_avatar_url: data.sender_avatar_url ?? undefined,
						body: data.body,
						type: data.msg_type,
						created_at: data.created_at,
						media: data.media ?? [],
						client_msg_id: data.client_msg_id ?? undefined
					});
					const idx = data.client_msg_id
						? messages.findIndex((m) => m.pending && m.client_msg_id === data.client_msg_id)
						: -1;
					messages = idx >= 0 ? messages.map((m, i) => (i === idx ? msg : m)) : [...messages, msg];
					if (stick) tick().then(scrollToBottom);
					// Only mark read when the message is actually in view: a message appended
					// while the user has scrolled up isn't brought into view, so reading it
					// would clear its unread state unseen. Scrolling back down marks it read.
					if (document.visibilityState === 'visible' && stick) {
						tryMarkRead();
					}
				} else if (data.type === 'system') {
					// e.g. "A posted a new topic!" reminder in the group main chat.
					messages = [
						...messages,
						{
							id: data.id ?? crypto.randomUUID(),
							chatroom_id: chatroomId,
							sender_id: null,
							body: data.body,
							type: 'system',
							created_at: data.created_at ?? new Date().toISOString()
						}
					];
					if (stick) tick().then(scrollToBottom);
				} else if (data.type === 'transcript') {
					// Async STT finished for a voice message (possibly one sent
					// minutes ago) — patch the media entry in place. No scroll:
					// the bubble grows a caption, the log must not jump.
					const owner = messages.find(
						(m) => m.id === data.message_id && m.media?.some((x) => x.id === data.media_id)
					);
					if (!owner) {
						// The frame beat its message (worker publish is unordered
						// with the echo/broadcast). Hold it; the insertion paths
						// apply it when the message shows up.
						pendingTranscripts.set(data.media_id, {
							status: data.status,
							transcript: data.transcript
						});
					} else {
						messages = messages.map((m) =>
							m.id === data.message_id && m.media?.some((x) => x.id === data.media_id)
								? {
										...m,
										media: m.media.map((x) =>
											x.id === data.media_id
												? { ...x, transcript: data.transcript, transcript_status: data.status }
												: x
										)
									}
								: m
						);
					}
				}
			} catch {
				// ignore parse errors
			}
		};

		socket.onclose = (event) => {
			connected = false;
			// 4001 = the server evicted us because we were removed from (or the
			// owner deleted) this group. Drop the now-inaccessible group's caches
			// and leave the group so we don't keep rendering stale chat/topics.
			if (event.code === EVICTED_CLOSE_CODE) {
				for (const key of [
					['group', groupId],
					['members', groupId],
					['topics', groupId],
					['topic-dates', groupId]
				]) {
					queryClient.removeQueries({ queryKey: key });
				}
				queryClient.removeQueries({ queryKey: ['topic'] });
				queryClient.removeQueries({ queryKey: ['messages'] });
				queryClient.invalidateQueries({ queryKey: ['groups'] });
				// eslint-disable-next-line svelte/no-navigation-without-resolve -- static route literal
				goto('/groups');
			}
		};

		ws = socket;

		return () => {
			socket.close();
			ws = null;
		};
	});

	// True when the viewport is at/near the newest message — used to decide
	// whether a live message should auto-scroll (stick) or preserve the reader's
	// position while they browse older history.
	function isNearBottom(): boolean {
		if (!messagesEl) return true;
		return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 120;
	}

	function scrollToBottom() {
		if (messagesEl) {
			messagesEl.scrollTop = messagesEl.scrollHeight;
		}
	}

	// Page in the previous batch of history and prepend it, keeping the viewport
	// anchored to the message the user was reading (no jump).
	async function loadOlder() {
		if (loadingOlder || !nextCursor || !chatroomId || !messagesEl) return;
		const cursor = nextCursor;
		const prevHeight = messagesEl.scrollHeight;
		const prevTop = messagesEl.scrollTop;
		loadingOlder = true;
		try {
			const olderPage = await listMessages(groupId, chatroomId, cursor);
			const older = [...olderPage.items].reverse(); // oldest-first
			const seen = new Set(messages.map((m) => m.id));
			// Claim buffered transcript frames here too: an older page's REST
			// snapshot can predate the worker's commit while the frame already
			// arrived (and was buffered) — every insertion path must drain the
			// buffer or that bubble sticks on "transcribing…".
			const fresh = older.filter((m) => !seen.has(m.id)).map(applyBufferedTranscripts);
			messages = [...fresh, ...messages];
			nextCursor = olderPage.next_cursor;
		} catch {
			// transient failure — the user can scroll up again to retry
		} finally {
			loadingOlder = false;
		}
		// Measure after the indicator is gone so its height doesn't skew the
		// anchor; restore the prior reading position now that content prepended.
		await tick();
		if (messagesEl) {
			messagesEl.scrollTop = messagesEl.scrollHeight - prevHeight + prevTop;
		}
	}

	function handleScroll() {
		if (messagesEl && messagesEl.scrollTop < 80 && nextCursor && !loadingOlder) {
			loadOlder();
		}
		// Scrolling back to the bottom means the newest messages are now in view —
		// mark read (covers messages that arrived while the user was scrolled up).
		if (document.visibilityState === 'visible' && isNearBottom()) {
			tryMarkRead();
		}
	}

	/**
	 * Queue a message on the socket. Returns whether it was actually sent — an
	 * upload can outlive the connection, and the composer must not discard the
	 * user's draft and previews for a send that silently no-opped.
	 */
	function sendMessage(body: string, media: ChatMediaInput[] = []): boolean {
		// A media-only message is valid, so body alone no longer gates the send.
		if ((!body && media.length === 0) || !ws || ws.readyState !== WebSocket.OPEN || !chatroomId)
			return false;

		const clientMsgId = crypto.randomUUID();
		const msg: WsClientMessage = {
			type: 'send_message',
			chatroom_id: chatroomId,
			body,
			client_msg_id: clientMsgId,
			...(media.length > 0 ? { media } : {})
		};
		ws.send(JSON.stringify(msg));

		messages = [
			...messages,
			{
				id: clientMsgId,
				chatroom_id: chatroomId,
				sender_id: null,
				body,
				type: 'text',
				created_at: new Date().toISOString(),
				// The objects are already uploaded, but only the server can issue
				// read URLs — so show a correctly-sized skeleton until the ack
				// swaps this row for the real, signed media.
				media: [],
				pendingMedia: media.map((m) => ({
					content_type: m.content_type,
					width: m.width,
					height: m.height
				})),
				client_msg_id: clientMsgId,
				pending: true
			}
		];
		scrollToBottom();
		return true;
	}

	// Transcript frames that arrived before the message they belong to. The
	// worker publishes through Redis on its own schedule — it is NOT ordered
	// with this handler's echo/broadcast — so a fast failure (or a very short
	// clip) can beat the `message` frame here. Dropping the frame would strand
	// the later-arriving bubble on "받아쓰는 중" until a reload; buffering by
	// media_id lets every message-insertion path claim it. Entries are removed
	// on match; the map only ever holds this room's still-unmatched frames.
	const pendingTranscripts = new SvelteMap<string, { status: string; transcript: string | null }>();

	function applyBufferedTranscripts(msg: ChatMessage): ChatMessage {
		if (!msg.media?.length || pendingTranscripts.size === 0) return msg;
		let changed = false;
		const media = msg.media.map((m) => {
			const buffered = pendingTranscripts.get(m.id);
			if (!buffered) return m;
			pendingTranscripts.delete(m.id);
			changed = true;
			return { ...m, transcript: buffered.transcript, transcript_status: buffered.status };
		});
		return changed ? { ...msg, media } : msg;
	}

	// Fullscreen viewer. Holds its own copy of the items so a URL refresh
	// mid-view cannot swap the picture under the user.
	let lightbox = $state<{ items: ChatMedia[]; index: number } | null>(null);

	function openLightbox(msg: ChatMessage, index: number) {
		if (!msg.media) return;
		lightbox = { items: msg.media, index };
	}

	/**
	 * Reissue ONE attachment's presigned URL. Signatures last 10 minutes while a
	 * chat window stays open for hours, so scrollback media will start failing.
	 *
	 * Per-attachment, not per-page: scrolling up loads older pages, and
	 * refetching just the newest page would never contain those messages — their
	 * pictures would stay broken for the rest of the session.
	 */
	const MAX_MEDIA_REFRESH_ATTEMPTS = 3;
	// SvelteMap/SvelteSet purely to satisfy svelte/prefer-svelte-reactivity —
	// nothing renders from these (pure bookkeeping), so the reactivity is
	// unused but harmless.
	const mediaRefreshAttempts = new SvelteMap<string, number>();
	const mediaRefreshInFlight = new SvelteSet<string>();

	/**
	 * An attachment rendered, so the URL it was given works — clear its strike
	 * count. The counter has to track CONSECUTIVE failures, not lifetime ones:
	 * over a multi-hour session a picture legitimately expires every 10 minutes,
	 * and a lifetime cap would permanently break it on the fourth expiry.
	 *
	 * Note this resets on the picture loading, NOT on the refresh call
	 * returning 200 — the endpoint signs from the DB row, so it happily hands
	 * back a URL for an object that is no longer in the bucket. Resetting on
	 * the API response would therefore restore the very loop the cap exists to
	 * prevent.
	 */
	function onMediaLoaded(mediaId: string) {
		mediaRefreshAttempts.delete(mediaId);
	}

	async function refreshMediaUrl(mediaId: string) {
		if (!chatroomId || mediaRefreshInFlight.has(mediaId)) return;
		// Bound consecutive failures per attachment: an object that is genuinely
		// gone (rather than merely expired) would otherwise loop
		// error → refresh → error for as long as it stays on screen.
		const attempts = mediaRefreshAttempts.get(mediaId) ?? 0;
		if (attempts >= MAX_MEDIA_REFRESH_ATTEMPTS) return;
		mediaRefreshAttempts.set(mediaId, attempts + 1);
		mediaRefreshInFlight.add(mediaId);
		try {
			const fresh = await refreshChatMediaUrl(groupId, chatroomId, mediaId);
			messages = messages.map((m) =>
				m.media?.some((x) => x.id === mediaId)
					? { ...m, media: m.media.map((x) => (x.id === mediaId ? fresh : x)) }
					: m
			);
		} catch {
			// Best-effort: a failed refresh just leaves the broken thumbnail.
		} finally {
			mediaRefreshInFlight.delete(mediaId);
		}
	}

	function hm(iso: string): string {
		return new Date(iso).toLocaleTimeString('ko-KR', {
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	// Local calendar-day key, so date dividers match the locally rendered times.
	function ymd(iso: string): string {
		const d = new Date(iso);
		return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
	}

	function dateLabel(iso: string): string {
		return new Date(iso).toLocaleDateString('ko-KR', {
			year: 'numeric',
			month: 'long',
			day: 'numeric'
		});
	}

	// Show a date divider above the first message and wherever the day changes.
	function showDateDivider(i: number): boolean {
		if (i === 0) return true;
		return ymd(messages[i].created_at) !== ymd(messages[i - 1].created_at);
	}

	// Avatar + nickname head each (sender, minute) group — a new header starts on
	// a sender change OR a new minute, so the sender is shown per minute block,
	// matching the minute-grouped timestamps below.
	function showHeader(i: number): boolean {
		const m = messages[i];
		if (m.type === 'system') return false;
		const prev = messages[i - 1];
		if (!prev || prev.type === 'system') return true;
		return prev.sender_id !== m.sender_id || hm(prev.created_at) !== hm(m.created_at);
	}

	// Time shows only on the last message of a same-minute run (dedupe HH:MM).
	function showTime(i: number): boolean {
		const m = messages[i];
		if (m.type === 'system') return false;
		const next = messages[i + 1];
		if (!next || next.type === 'system') return true;
		return hm(next.created_at) !== hm(m.created_at);
	}

	function initial(name: string | undefined): string {
		return name?.trim()?.[0]?.toUpperCase() ?? '?';
	}
</script>

{#snippet messageBody(msg: ChatMessage, onPrimary: boolean)}
	{#if msg.pendingMedia && msg.pendingMedia.length > 0}
		<MessageMedia pending={msg.pendingMedia} />
	{:else if msg.media && msg.media.length > 0}
		<MessageMedia
			media={msg.media}
			onopen={(i) => openLightbox(msg, i)}
			onexpired={refreshMediaUrl}
			onloaded={onMediaLoaded}
		/>
	{/if}
	{#if msg.body}
		<div
			class="chat-message-prose prose max-w-none wrap-anywhere {onPrimary
				? 'prose-primary-content'
				: ''} [&_a]:font-normal [&_pre]:overflow-x-auto [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
		>
			<!-- eslint-disable-next-line svelte/no-at-html-tags -- output sanitized by renderMarkdown (DOMPurify) -->
			{@html renderMarkdown(msg.body)}
		</div>
	{/if}
{/snippet}

<div
	bind:this={rootEl}
	class="fixed inset-y-0 right-0 left-0 flex flex-col bg-base-100 will-change-transform lg:left-[var(--rail-width)]"
	style="height: 100dvh"
>
	<AppHeader>
		<div class="mx-auto flex w-full max-w-[720px] items-center gap-3">
			<button onclick={goBack} class="btn -ml-2 btn-square btn-ghost" aria-label="뒤로 가기">
				<ArrowLeft class="h-5 w-5" />
			</button>
			<div class="flex min-w-0 flex-1 items-center gap-1">
				<h1
					data-route-focus-target
					tabindex="-1"
					class="min-w-0 truncate text-base font-semibold text-base-content"
				>
					{title}
				</h1>
				{#if canRenameTitle}
					<button
						type="button"
						onclick={onRenameTitle}
						class="btn btn-square size-11 min-h-11 shrink-0 btn-ghost"
						aria-label="주제 이름 수정"
					>
						<Pencil class="h-4 w-4" />
					</button>
				{/if}
				{#if pinnedBody}
					<button
						type="button"
						onclick={() => (bodyOpen = !bodyOpen)}
						class="btn btn-square size-11 min-h-11 shrink-0 btn-ghost"
						aria-expanded={bodyOpen}
						aria-controls="topic-body"
						aria-label={bodyOpen ? '본문 접기' : '본문 펼치기'}
					>
						<ChevronDown
							class="h-4 w-4 transition-transform duration-[var(--duration-standard)] {bodyOpen
								? 'rotate-180'
								: ''}"
						/>
					</button>
				{/if}
			</div>
			{#if canEditPinned && !pinnedBody}
				<button
					type="button"
					onclick={onEditPinned}
					class="btn min-h-11 shrink-0 btn-ghost px-3 text-primary"
					aria-label="본문 추가"
				>
					본문 추가
				</button>
			{/if}
			<div
				class="status shrink-0 {connected ? 'status-success' : ''}"
				role="status"
				aria-label={connected ? '연결됨' : '연결 중'}
				aria-live="polite"
				title={connected ? '연결됨' : '연결 중...'}
			></div>
		</div>
	</AppHeader>

	{#if pinnedBody}
		<div
			id="topic-body"
			hidden={!bodyOpen}
			class="shrink-0 border-b border-base-300 bg-base-200 px-4 py-3"
		>
			<div class="mx-auto flex w-full max-w-[720px] items-start gap-2">
				<div class="max-h-40 min-w-0 flex-1 overflow-y-auto">
					<div
						class="prose max-w-none [&_pre]:overflow-x-auto [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
					>
						<!-- eslint-disable-next-line svelte/no-at-html-tags -- output sanitized by renderMarkdown (DOMPurify) -->
						{@html renderMarkdown(pinnedBody)}
					</div>
				</div>
				{#if canEditPinned}
					<button
						onclick={onEditPinned}
						class="btn min-h-11 shrink-0 btn-ghost px-3 text-primary"
						aria-label="본문 수정"
					>
						수정
					</button>
				{/if}
			</div>
		</div>
	{/if}

	<main
		id="main-content"
		bind:this={messagesEl}
		onscroll={handleScroll}
		class="flex-1 overflow-y-auto overscroll-contain px-4 py-4 md:px-6"
		aria-label="채팅 메시지"
		aria-live="polite"
		aria-atomic="false"
		tabindex="-1"
	>
		<div
			class="mx-auto w-full max-w-[720px] space-y-3 {messages.length > 0 && !initialReady
				? 'opacity-0'
				: ''}"
		>
			{#if loadingOlder}
				<p class="py-1 text-center text-xs text-[var(--color-text-muted)]">
					이전 메시지 불러오는 중...
				</p>
			{/if}
			{#if messagesQuery.isPending && messages.length === 0}
				<p class="py-8 text-center text-sm text-[var(--color-text-muted)]">불러오는 중...</p>
			{:else if messages.length === 0}
				<p class="py-8 text-center text-sm text-[var(--color-text-muted)]">
					첫 메시지를 남겨보세요
				</p>
			{:else}
				{#each messages as msg, i (msg.id)}
					{#if showDateDivider(i)}
						<div class="divider my-1 text-[13px] text-[var(--color-text-muted)] tabular-nums">
							{dateLabel(msg.created_at)}
						</div>
					{/if}
					{#if msg.type === 'system'}
						<div class="text-center">
							<span class="badge h-6 badge-ghost text-[13px]">{msg.body}</span>
						</div>
					{:else if isMine(msg)}
						<div class="chat-end chat py-0 {!showHeader(i) ? '-mt-2' : ''}">
							<div
								class="chat-bubble-primary-readable chat-bubble max-w-[78%] rounded-[20px_20px_8px_20px] chat-bubble-primary text-base leading-[1.55] before:hidden lg:max-w-[66%]"
							>
								{@render messageBody(msg, true)}
							</div>
							{#if msg.pending}
								<div
									class="chat-footer text-[13px] text-[var(--color-text-muted)] tabular-nums"
									aria-live="polite"
								>
									전송 중
								</div>
							{:else if showTime(i)}
								<div class="chat-footer text-[13px] text-[var(--color-text-muted)] tabular-nums">
									{hm(msg.created_at)}
								</div>
							{/if}
						</div>
					{:else}
						<div class="chat-start chat py-0 {!showHeader(i) ? '-mt-2' : ''}">
							<div
								class="avatar chat-image {msg.sender_avatar_url ? '' : 'avatar-placeholder'} w-8"
							>
								{#if showHeader(i)}
									{#if msg.sender_avatar_url}
										<div class="w-8 rounded-full">
											<img src={msg.sender_avatar_url} alt={msg.sender_nickname ?? ''} />
										</div>
									{:else}
										<div class="w-8 rounded-full bg-primary/20 text-primary" aria-hidden="true">
											<span class="text-xs font-semibold">{initial(msg.sender_nickname)}</span>
										</div>
									{/if}
								{/if}
							</div>
							{#if showHeader(i) && msg.sender_nickname}
								<div class="chat-header text-[13px] text-[var(--color-text-muted)]">
									{msg.sender_nickname}
								</div>
							{/if}
							<div
								class="chat-bubble max-w-[78%] rounded-[20px_20px_20px_8px] bg-[var(--color-surface-raised)] text-base leading-[1.55] text-base-content before:hidden lg:max-w-[66%]"
							>
								{@render messageBody(msg, false)}
							</div>
							{#if showTime(i)}
								<div class="chat-footer text-[13px] text-[var(--color-text-muted)] tabular-nums">
									{hm(msg.created_at)}
								</div>
							{/if}
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</main>

	<ChatComposer {groupId} {chatroomId} {connected} {keyboardOpen} onsend={sendMessage} />
</div>

{#if lightbox}
	<MediaLightbox
		{groupId}
		{chatroomId}
		items={lightbox.items}
		startIndex={lightbox.index}
		onclose={() => (lightbox = null)}
	/>
{/if}
