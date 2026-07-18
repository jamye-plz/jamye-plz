<script lang="ts">
	import { tick, untrack } from 'svelte';
	import { createQuery, useQueryClient } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { listMessages, markChatroomRead } from '$lib/api/chat.api';
	import { renderMarkdown } from '$lib/markdown';
	import { getMe } from '$lib/api/auth.api';
	import type { ChatMessage, WsClientMessage, WsServerMessage } from '$lib/types/chat.types';
	import ArrowLeft from '@lucide/svelte/icons/arrow-left';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';

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
		createdAt
	}: {
		groupId: string;
		chatroomId: string;
		title: string;
		backHref: string;
		pinnedBody?: string | null;
		canEditPinned?: boolean;
		onEditPinned?: () => void;
		/** Room (topic/chatroom) creation time — the read bound for an empty room. */
		createdAt?: string;
	} = $props();

	const queryClient = useQueryClient();

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
	let inputText = $state('');
	let ws = $state<WebSocket | null>(null);
	let connected = $state(false);
	let messagesEl = $state<HTMLElement | null>(null);
	let inputEl = $state<HTMLTextAreaElement | null>(null);

	// Auto-grow the composer with its content (up to ~6 lines, then it scrolls).
	$effect(() => {
		inputText; // track changes (incl. reset after send)
		if (inputEl) {
			inputEl.style.height = 'auto';
			inputEl.style.height = `${Math.min(inputEl.scrollHeight, 160)}px`;
		}
	});

	// Seed the room from the latest page (newest-first → reversed to oldest-first
	// for display) and remember the cursor to older history. Mid-session refetch
	// is disabled, so this only runs on entry — then WS + loadOlder own `messages`.
	$effect(() => {
		if (messagesQuery.data) {
			messages = [...messagesQuery.data.items].reverse();
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
					const missed = page.items.filter((m) => !have.has(m.id));
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
					const msg: ChatMessage = {
						id: data.id,
						chatroom_id: data.chatroom_id,
						sender_id: data.sender_id,
						sender_nickname: data.sender_nickname ?? undefined,
						sender_avatar_url: data.sender_avatar_url ?? undefined,
						body: data.body,
						type: data.msg_type,
						created_at: data.created_at,
						client_msg_id: data.client_msg_id ?? undefined
					};
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
				}
			} catch {
				// ignore parse errors
			}
		};

		socket.onclose = () => {
			connected = false;
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
			const fresh = older.filter((m) => !seen.has(m.id));
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

	function sendMessage() {
		const body = inputText.trim();
		if (!body || !ws || ws.readyState !== WebSocket.OPEN || !chatroomId) return;

		const clientMsgId = crypto.randomUUID();
		const msg: WsClientMessage = {
			type: 'send_message',
			chatroom_id: chatroomId,
			body,
			client_msg_id: clientMsgId
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
				client_msg_id: clientMsgId,
				pending: true
			}
		];
		inputText = '';
		scrollToBottom();
	}

	function handleKeydown(e: KeyboardEvent) {
		// Ignore Enter while an IME composition is active (Korean/Japanese/Chinese):
		// that Enter commits the composition, and sending on it duplicates the last
		// syllable (e.g. "안녕" sent, then the committed "녕" sent again). The next,
		// non-composing Enter is the real send.
		if (e.isComposing || e.keyCode === 229) return;
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
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

{#snippet messageBody(body: string, onPrimary: boolean)}
	<div
		class="prose prose-sm max-w-none wrap-anywhere {onPrimary
			? 'prose-primary-content'
			: ''} [&_a]:font-normal [&_pre]:overflow-x-auto [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
	>
		{@html renderMarkdown(body)}
	</div>
{/snippet}

<div class="flex h-screen flex-col bg-base-100">
	<header
		class="navbar sticky top-0 z-10 shrink-0 border-b border-base-300 bg-base-100/80 backdrop-blur"
	>
		<div class="mx-auto flex w-full max-w-2xl items-center gap-3">
			<button
				onclick={() => goto(backHref)}
				class="btn -ml-2 btn-square btn-ghost btn-sm"
				aria-label="뒤로 가기"
			>
				<ArrowLeft class="h-5 w-5" />
			</button>
			<div class="min-w-0 flex-1">
				<h1 class="truncate text-base font-semibold text-base-content">
					{title}
				</h1>
			</div>
			<div
				class="status shrink-0 {connected ? 'status-success' : ''}"
				aria-label={connected ? '연결됨' : '연결 중'}
				title={connected ? '연결됨' : '연결 중...'}
			></div>
		</div>
	</header>

	{#if pinnedBody || canEditPinned}
		<div class="shrink-0 border-b border-base-300 bg-base-200 px-4 py-3">
			<div class="mx-auto flex w-full max-w-2xl items-start gap-2">
				<div class="max-h-40 min-w-0 flex-1 overflow-y-auto">
					{#if pinnedBody}
						<div
							class="prose prose-sm max-w-none [&_pre]:overflow-x-auto [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
						>
							{@html renderMarkdown(pinnedBody)}
						</div>
					{:else}
						<p class="text-sm text-base-content/50 italic">아직 본문이 없어요</p>
					{/if}
				</div>
				{#if canEditPinned}
					<button onclick={onEditPinned} class="btn shrink-0 btn-ghost text-primary btn-xs">
						{pinnedBody ? '수정' : '본문 추가'}
					</button>
				{/if}
			</div>
		</div>
	{/if}

	<section
		bind:this={messagesEl}
		onscroll={handleScroll}
		class="flex-1 overflow-y-auto px-4 py-4"
		aria-label="채팅 메시지"
		aria-live="polite"
		aria-atomic="false"
	>
		<div
			class="mx-auto w-full max-w-2xl space-y-3 {messages.length > 0 && !initialReady
				? 'opacity-0'
				: ''}"
		>
			{#if loadingOlder}
				<p class="py-1 text-center text-xs text-base-content/50">이전 메시지 불러오는 중...</p>
			{/if}
			{#if messagesQuery.isPending && messages.length === 0}
				<p class="py-8 text-center text-sm text-base-content/70">불러오는 중...</p>
			{:else if messages.length === 0}
				<p class="py-8 text-center text-sm text-base-content/50">첫 메시지를 남겨보세요</p>
			{:else}
				{#each messages as msg, i (msg.id)}
					{#if showDateDivider(i)}
						<div class="divider my-1 text-[11px] text-base-content/50">
							{dateLabel(msg.created_at)}
						</div>
					{/if}
					{#if msg.type === 'system'}
						<div class="text-center">
							<span class="badge badge-ghost badge-sm">{msg.body}</span>
						</div>
					{:else if isMine(msg)}
						<div class="chat-end chat {!showHeader(i) ? '-mt-3' : ''}">
							<div
								class="chat-bubble-primary-readable chat-bubble chat-bubble-primary text-sm {msg.pending
									? 'opacity-60'
									: ''}"
							>
								{@render messageBody(msg.body, true)}
							</div>
							{#if showTime(i)}
								<div class="chat-footer text-[10px] text-base-content/50">
									{hm(msg.created_at)}
								</div>
							{/if}
						</div>
					{:else}
						<div class="chat-start chat {!showHeader(i) ? '-mt-3' : ''}">
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
								<div class="chat-header text-xs text-base-content/50">
									{msg.sender_nickname}
								</div>
							{/if}
							<div class="chat-bubble text-sm">
								{@render messageBody(msg.body, false)}
							</div>
							{#if showTime(i)}
								<div class="chat-footer text-[10px] text-base-content/50">
									{hm(msg.created_at)}
								</div>
							{/if}
						</div>
					{/if}
				{/each}
			{/if}
		</div>
	</section>

	<footer class="shrink-0 border-t border-base-300 bg-base-100 px-4 py-3">
		<div class="mx-auto flex max-w-2xl items-end gap-2">
			<textarea
				bind:this={inputEl}
				bind:value={inputText}
				onkeydown={handleKeydown}
				placeholder="메시지 입력..."
				rows={1}
				class="textarea max-h-40 flex-1 resize-none overflow-y-auto focus:border-primary focus:outline-none!"
				aria-label="메시지 입력"></textarea>
			<button
				onclick={sendMessage}
				disabled={!inputText.trim() || !connected}
				class="btn btn-square shrink-0 btn-primary"
				aria-label="메시지 보내기"
			>
				<ArrowUp class="h-5 w-5" />
			</button>
		</div>
	</footer>
</div>
