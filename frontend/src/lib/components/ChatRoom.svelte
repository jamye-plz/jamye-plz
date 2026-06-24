<script lang="ts">
	import { tick } from 'svelte';
	import { createQuery } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { listMessages } from '$lib/api/chat.api';
	import { getMe } from '$lib/api/auth.api';
	import type { ChatMessage, WsClientMessage, WsServerMessage } from '$lib/types/chat.types';

	// A single chatroom view (history + live WS + composer). Reused by the group
	// main chat and per-topic chat — each is an isolated room keyed by chatroomId.
	let {
		groupId,
		chatroomId,
		title,
		backHref,
		pinnedBody,
		canEditPinned = false,
		onEditPinned
	}: {
		groupId: string;
		chatroomId: string;
		title: string;
		backHref: string;
		pinnedBody?: string | null;
		canEditPinned?: boolean;
		onEditPinned?: () => void;
	} = $props();

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
		}
	});

	$effect(() => {
		if (!chatroomId) return;

		const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
		const socket = new WebSocket(`${protocol}://${window.location.host}/api/ws`);

		socket.onopen = () => {
			connected = true;
			const joinMsg: WsClientMessage = { type: 'join', chatroom_id: chatroomId };
			socket.send(JSON.stringify(joinMsg));
		};

		socket.onmessage = (event) => {
			try {
				const data: WsServerMessage = JSON.parse(event.data as string);
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
					scrollToBottom();
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
					scrollToBottom();
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
		return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
	}

	// Split a message body into text + link segments: markdown links [text](href)
	// and bare http(s) URLs. Internal hrefs (starting with "/") navigate via the
	// SPA; external ones open in a new tab.
	type BodySeg = { text: string; href?: string; internal?: boolean };
	function linkify(body: string): BodySeg[] {
		const segs: BodySeg[] = [];
		const re = /\[([^\]]+)\]\((\/[^\s)]+|https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s]+)/g;
		let last = 0;
		let m: RegExpExecArray | null;
		while ((m = re.exec(body)) !== null) {
			if (m.index > last) segs.push({ text: body.slice(last, m.index) });
			if (m[1] !== undefined) {
				segs.push({ text: m[1], href: m[2], internal: m[2].startsWith('/') });
			} else {
				segs.push({ text: m[3], href: m[3], internal: false });
			}
			last = re.lastIndex;
		}
		if (last < body.length) segs.push({ text: body.slice(last) });
		return segs;
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

{#snippet messageBody(body: string, linkClass: string)}
	{#each linkify(body) as seg}
		{#if seg.href && seg.internal}
			<a
				href={seg.href}
				onclick={(e) => {
					e.preventDefault();
					goto(seg.href!);
				}}
				class={linkClass}>{seg.text}</a
			>
		{:else if seg.href}
			<a href={seg.href} target="_blank" rel="noopener noreferrer" class={linkClass}>{seg.text}</a>
		{:else}{seg.text}{/if}
	{/each}
{/snippet}

<div class="flex flex-col h-screen bg-background">
	<header
		class="shrink-0 sticky top-0 z-10 bg-background/80 backdrop-blur border-b border-border px-4 py-3"
	>
		<div class="mx-auto w-full max-w-2xl flex items-center gap-3">
			<button
				onclick={() => goto(backHref)}
				class="p-2 -ml-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-colors"
				aria-label="뒤로 가기"
			>
				←
			</button>
			<div class="flex-1 min-w-0">
				<h1 class="text-base font-semibold text-text-primary truncate">{title}</h1>
			</div>
			<div
				class="w-2 h-2 rounded-full shrink-0 {connected ? 'bg-success' : 'bg-text-muted'}"
				aria-label={connected ? '연결됨' : '연결 중'}
				title={connected ? '연결됨' : '연결 중...'}
			></div>
		</div>
	</header>

	{#if pinnedBody || canEditPinned}
		<div class="shrink-0 border-b border-border bg-surface px-4 py-3">
			<div class="mx-auto w-full max-w-2xl flex items-start gap-2">
				<div class="flex-1 min-w-0 max-h-40 overflow-y-auto">
					{#if pinnedBody}
						<p class="text-sm text-text-secondary leading-relaxed whitespace-pre-wrap">{pinnedBody}</p>
					{:else}
						<p class="text-sm text-text-muted italic">아직 본문이 없어요</p>
					{/if}
				</div>
				{#if canEditPinned}
					<button
						onclick={onEditPinned}
						class="shrink-0 text-xs font-medium text-accent hover:text-accent-hover transition-colors focus-visible:outline-2 focus-visible:outline-accent rounded px-1"
					>
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
			<p class="text-text-muted text-xs text-center py-1">이전 메시지 불러오는 중...</p>
		{/if}
		{#if messagesQuery.isPending && messages.length === 0}
			<p class="text-text-secondary text-sm text-center py-8">불러오는 중...</p>
		{:else if messages.length === 0}
			<p class="text-text-muted text-sm text-center py-8">첫 메시지를 남겨보세요</p>
		{:else}
			{#each messages as msg, i (msg.id)}
					{#if showDateDivider(i)}
						<div class="flex justify-center py-1">
							<span class="text-[11px] text-text-muted bg-surface px-3 py-1 rounded-full">
								{dateLabel(msg.created_at)}
							</span>
						</div>
					{/if}
					{#if msg.type === 'system'}
						<div class="text-center">
							<span class="text-xs text-text-muted bg-surface px-3 py-1 rounded-full"
								>{@render messageBody(msg.body, 'text-accent underline decoration-2 underline-offset-2 hover:opacity-80')}</span
							>
						</div>
					{:else if isMine(msg)}
						<div class="flex items-end justify-end gap-1.5">
							{#if showTime(i)}
								<span class="text-[10px] text-text-muted shrink-0 pb-1">{hm(msg.created_at)}</span>
							{/if}
							<div
								class="max-w-[75%] px-3 py-2 rounded-2xl text-sm leading-relaxed break-words bg-accent text-white rounded-br-sm {msg.pending ? 'opacity-60' : ''}"
							>
								{@render messageBody(msg.body, 'text-[#67e8f9] underline decoration-2 underline-offset-2 hover:opacity-80')}
							</div>
						</div>
					{:else}
						<div class="flex items-start gap-2">
							<div class="w-8 shrink-0">
								{#if showHeader(i)}
									{#if msg.sender_avatar_url}
										<img
											src={msg.sender_avatar_url}
											alt={msg.sender_nickname ?? ''}
											class="w-8 h-8 rounded-full object-cover bg-surface-elevated"
										/>
									{:else}
										<div
											class="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center text-xs font-semibold"
											aria-hidden="true"
										>
											{initial(msg.sender_nickname)}
										</div>
									{/if}
								{/if}
							</div>
							<div class="flex-1 min-w-0 space-y-0.5">
								{#if showHeader(i) && msg.sender_nickname}
									<span class="block text-xs text-text-muted px-1">{msg.sender_nickname}</span>
								{/if}
								<div class="flex items-end gap-1.5">
									<div
										class="max-w-[75%] px-3 py-2 rounded-2xl text-sm leading-relaxed break-words bg-surface-elevated text-text-primary rounded-bl-sm"
									>
										{@render messageBody(msg.body, 'text-accent underline decoration-2 underline-offset-2 hover:opacity-80')}
									</div>
									{#if showTime(i)}
										<span class="text-[10px] text-text-muted shrink-0 pb-1">{hm(msg.created_at)}</span>
									{/if}
								</div>
							</div>
						</div>
					{/if}
				{/each}
		{/if}
		</div>
	</section>

	<footer class="shrink-0 border-t border-border px-4 py-3 bg-background">
		<div class="flex items-end gap-2 max-w-2xl mx-auto">
			<textarea
				bind:this={inputEl}
				bind:value={inputText}
				onkeydown={handleKeydown}
				placeholder="메시지 입력..."
				rows={1}
				class="flex-1 resize-none px-3 py-2 rounded-xl bg-surface-elevated border border-border text-text-primary placeholder:text-text-muted text-sm focus-visible:outline-2 focus-visible:outline-accent max-h-40 overflow-y-auto"
				aria-label="메시지 입력"
			></textarea>
			<button
				onclick={sendMessage}
				disabled={!inputText.trim() || !connected}
				class="shrink-0 p-2.5 rounded-xl bg-accent text-white disabled:opacity-40 transition-opacity hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-accent"
				aria-label="메시지 보내기"
			>
				↑
			</button>
		</div>
	</footer>
</div>
