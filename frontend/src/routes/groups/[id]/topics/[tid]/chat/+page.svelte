<script lang="ts">
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { page } from '$app/state';
	import { getTopic, enrichTopic } from '$lib/api/topic.api';
	import { getMe } from '$lib/api/auth.api';
	import ChatRoom from '$lib/components/ChatRoom.svelte';

	const groupId = $derived(page.params.id!);
	const topicId = $derived(page.params.tid!);
	const queryClient = useQueryClient();

	const topicQuery = createQuery(() => ({
		queryKey: ['topic', topicId],
		queryFn: () => getTopic(groupId, topicId)
	}));
	const meQuery = createQuery(() => ({ queryKey: ['me'], queryFn: getMe }));

	// Per-topic chatroom: a separate room scoped to this topic, isolated from the
	// group main chat (content is not shared between the two).
	const chatroomId = $derived(topicQuery.data?.chatroom_id ?? '');

	// In-page back returns to the topic list on the right date. Prefer the date the
	// user came from (?date=); when arriving from a notification (no param), fall
	// back to the topic's own posting date (Asia/Seoul, matching the date strip).
	function seoulDate(iso: string): string {
		return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date(iso));
	}
	const backDate = $derived(
		page.url.searchParams.get('date') ??
			(topicQuery.data ? seoulDate(topicQuery.data.created_at) : null)
	);
	const backHref = $derived(
		`/groups/${groupId}${backDate ? `?date=${encodeURIComponent(backDate)}` : ''}`
	);

	// Only the topic author may add/edit the body (enrich).
	const isAuthor = $derived(
		!!topicQuery.data && !!meQuery.data && topicQuery.data.author_id === meQuery.data.id
	);

	let editDialog = $state<HTMLDialogElement | null>(null);
	let editorBody = $state('');

	function openEditor() {
		editorBody = topicQuery.data?.body ?? '';
		editDialog?.showModal();
	}

	const enrich = createMutation(() => ({
		mutationFn: (body: string) => enrichTopic(groupId, topicId, body),
		onSuccess: (topic) => {
			queryClient.setQueryData(['topic', topicId], topic);
			editDialog?.close();
		}
	}));

	function saveBody(e: SubmitEvent) {
		e.preventDefault();
		const body = editorBody.trim();
		if (!body || enrich.isPending) return;
		enrich.mutate(body);
	}
</script>

<ChatRoom
	{groupId}
	{chatroomId}
	title={topicQuery.data?.title ?? '주제 채팅'}
	pinnedBody={topicQuery.data?.body}
	canEditPinned={isAuthor}
	onEditPinned={openEditor}
	createdAt={topicQuery.data?.created_at}
	{backHref}
/>

<dialog
	bind:this={editDialog}
	class="modal modal-bottom sm:modal-middle"
	aria-labelledby="edit-body-title"
>
	<div class="modal-box space-y-4">
		<h2 id="edit-body-title" class="text-base font-semibold text-base-content">
			본문 {topicQuery.data?.body ? '수정' : '추가'}
		</h2>
		<form onsubmit={saveBody} class="space-y-3">
			<textarea
				bind:value={editorBody}
				placeholder="주제에 대한 내용을 적어주세요..."
				rows={6}
				class="textarea w-full resize-none focus:border-primary focus:outline-none!"></textarea>
			{#if enrich.isError}
				<p class="text-xs text-error" role="alert">저장에 실패했어요. 다시 시도해 주세요.</p>
			{/if}
			<div class="modal-action gap-2">
				<button type="button" onclick={() => editDialog?.close()} class="btn flex-1"> 취소 </button>
				<button
					type="submit"
					disabled={!editorBody.trim() || enrich.isPending}
					class="btn flex-1 btn-primary"
				>
					{enrich.isPending ? '저장 중...' : '저장'}
				</button>
			</div>
		</form>
	</div>
	<form method="dialog" class="modal-backdrop"><button aria-label="닫기">close</button></form>
</dialog>
