<script lang="ts">
	import { createQuery } from '@tanstack/svelte-query';
	import { goto } from '$app/navigation';
	import { listMessages } from '$lib/api/chat.api';
	import type { ChatMessage, WsClientMessage, WsServerMessage } from '$lib/types/chat.types';

	// A single chatroom view (history + live WS + composer). Reused by the group
	// main chat and per-topic chat — each is an isolated room keyed by chatroomId.
	let {
		groupId,
		chatroomId,
		title,
		backHref
	}: { groupId: string; chatroomId: string; title: string; backHref: string } = $props();

	const messagesQuery = createQuery(() => ({
		queryKey: ['messages', chatroomId],
		queryFn: () =>
			chatroomId
				? listMessages(groupId, chatroomId)
				: Promise.resolve({ items: [], next_cursor: null }),
		enabled: !!chatroomId
	}));

	let messages = $state<ChatMessage[]>([]);
	let inputText = $state('');
	let ws = $state<WebSocket | null>(null);
	let connected = $state(false);
	let messagesEl = $state<HTMLElement | null>(null);

	$effect(() => {
		if (messagesQuery.data) {
			messages = [...messagesQuery.data.items].reverse();
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
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}
</script>

<div class="flex flex-col h-screen bg-background">
	<header
		class="shrink-0 sticky top-0 z-10 bg-background/80 backdrop-blur border-b border-border px-4 py-3 flex items-center gap-3"
	>
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
	</header>

	<section
		bind:this={messagesEl}
		class="flex-1 overflow-y-auto px-4 py-4 space-y-3"
		aria-label="채팅 메시지"
		aria-live="polite"
		aria-atomic="false"
	>
		{#if messagesQuery.isPending && messages.length === 0}
			<p class="text-text-secondary text-sm text-center py-8">불러오는 중...</p>
		{:else if messages.length === 0}
			<p class="text-text-muted text-sm text-center py-8">첫 메시지를 남겨보세요</p>
		{:else}
			{#each messages as msg (msg.id)}
				{#if msg.type === 'system'}
					<div class="text-center">
						<span class="text-xs text-text-muted bg-surface px-3 py-1 rounded-full">{msg.body}</span>
					</div>
				{:else}
					<div class="flex gap-2 {msg.sender_id === null ? 'justify-end' : 'justify-start'}">
						<div
							class="max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed
								{msg.sender_id === null
								? 'bg-accent text-white rounded-br-sm'
								: 'bg-surface-elevated text-text-primary rounded-bl-sm'}
								{msg.pending ? 'opacity-60' : ''}"
						>
							{msg.body}
						</div>
					</div>
				{/if}
			{/each}
		{/if}
	</section>

	<footer class="shrink-0 border-t border-border px-4 py-3 bg-background">
		<div class="flex items-end gap-2 max-w-lg mx-auto">
			<textarea
				bind:value={inputText}
				onkeydown={handleKeydown}
				placeholder="메시지 입력..."
				rows={1}
				class="flex-1 resize-none px-3 py-2 rounded-xl bg-surface-elevated border border-border text-text-primary placeholder:text-text-muted text-sm focus-visible:outline-2 focus-visible:outline-accent max-h-32 overflow-y-auto"
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
